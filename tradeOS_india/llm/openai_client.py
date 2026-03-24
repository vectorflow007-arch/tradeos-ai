"""
TradeOS India — OpenAI (GPT-4o) LLM client.

Uses gpt-4o via the openai SDK. API key loaded from OS keyring.
Retries with exponential backoff on rate limit and API errors.
Logs every call to the llm_messages DB table and emits tokens_updated signal.
"""

import asyncio
import time
import uuid
from typing import AsyncIterator

from llm.base_llm import BaseLLM
from core.event_bus import EventBus
from core.state_store import AppState
from utils.keychain import get_secret
from utils.logger import get_logger

log = get_logger("llm.openai_client")

_MODEL = "gpt-4o"
_KEYRING_KEY = "tradeOS_openai_key"
_COST_PER_1K_INR = 1.1
_MAX_RETRIES = 3
_INITIAL_BACKOFF_S = 1.0


class OpenAIClient(BaseLLM):
    """OpenAI GPT-4o LLM client.

    Loads API key from OS keyring, uses gpt-4o,
    retries on transient errors, and logs usage to DB.
    """

    def __init__(self) -> None:
        self._client = None
        self._api_key: str = ""
        self._event_bus = EventBus.get_instance()
        self._state = AppState.get_instance()

    # ═════════════════════════════════════════════════════════════
    # Properties
    # ═════════════════════════════════════════════════════════════

    @property
    def model_name(self) -> str:
        """Return the OpenAI model identifier."""
        return _MODEL

    @property
    def provider(self) -> str:
        """Return the provider name."""
        return "openai"

    @property
    def cost_per_1k_tokens_inr(self) -> float:
        """Return cost per 1K tokens in INR."""
        return _COST_PER_1K_INR

    # ═════════════════════════════════════════════════════════════
    # Initialization
    # ═════════════════════════════════════════════════════════════

    def _ensure_client(self) -> bool:
        """Initialize the OpenAI client if not already done.

        Returns:
            True if client is ready.
        """
        if self._client is not None:
            return True

        self._api_key = get_secret(_KEYRING_KEY) or ""
        if not self._api_key:
            log.warning("OpenAI API key not found in keyring")
            return False

        try:
            import openai
            self._client = openai.AsyncOpenAI(api_key=self._api_key)
            log.info("OpenAI client initialized")
            return True
        except ImportError:
            log.error("openai SDK not installed")
            return False
        except Exception as exc:
            log.error(f"Failed to init OpenAI client: {exc}")
            return False

    # ═════════════════════════════════════════════════════════════
    # Complete
    # ═════════════════════════════════════════════════════════════

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1000,
    ) -> str:
        """Send a completion request to OpenAI.

        Retries up to 3 times with exponential backoff on transient errors.

        Args:
            system: System prompt.
            user: User message.
            max_tokens: Max response tokens.

        Returns:
            Response text string.
        """
        if not self._ensure_client():
            return '{"error": "OpenAI client not initialized"}'

        session_id = uuid.uuid4().hex[:12]
        start_ms = time.monotonic()
        backoff = _INITIAL_BACKOFF_S

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                import openai

                response = await self._client.chat.completions.create(
                    model=_MODEL,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )

                choice = response.choices[0] if response.choices else None
                text = choice.message.content if choice else ""
                tokens_in = response.usage.prompt_tokens if response.usage else 0
                tokens_out = (
                    response.usage.completion_tokens if response.usage else 0
                )
                duration_ms = int((time.monotonic() - start_ms) * 1000)
                total_tokens = tokens_in + tokens_out
                cost_inr = (total_tokens / 1000.0) * _COST_PER_1K_INR

                # Update state
                self._state.tokens_used_today += total_tokens
                self._state.cost_inr_today += cost_inr

                # Emit signal
                self._event_bus.tokens_updated.emit(
                    self._state.tokens_used_today,
                    self._state.cost_inr_today,
                )

                # Log to DB
                await self._log_message(
                    session_id=session_id,
                    system_prompt=system,
                    user_prompt=user,
                    response_text=text or "",
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_inr=cost_inr,
                    duration_ms=duration_ms,
                )

                log.debug(
                    f"OpenAI complete: {tokens_in}+{tokens_out} tokens, "
                    f"{duration_ms}ms, INR {cost_inr:.2f}"
                )
                return text or ""

            except openai.RateLimitError as exc:
                log.warning(
                    f"OpenAI rate limit (attempt {attempt}/{_MAX_RETRIES}): {exc}"
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    return '{"error": "Rate limit exceeded after retries"}'

            except openai.APIError as exc:
                log.error(
                    f"OpenAI API error (attempt {attempt}/{_MAX_RETRIES}): {exc}"
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    return f'{{"error": "API error: {str(exc)[:100]}"}}'

            except Exception as exc:
                log.error(f"OpenAI unexpected error: {exc}")
                return f'{{"error": "{str(exc)[:100]}"}}'

        return '{"error": "Max retries exceeded"}'

    # ═════════════════════════════════════════════════════════════
    # Stream
    # ═════════════════════════════════════════════════════════════

    async def stream(
        self,
        system: str,
        user: str,
    ) -> AsyncIterator[str]:
        """Stream a response from OpenAI, yielding text chunks.

        Args:
            system: System prompt.
            user: User message.

        Yields:
            Text chunks as they arrive.
        """
        if not self._ensure_client():
            yield '{"error": "OpenAI client not initialized"}'
            return

        try:
            import openai

            stream = await self._client.chat.completions.create(
                model=_MODEL,
                max_tokens=2000,
                stream=True,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except openai.RateLimitError as exc:
            log.warning(f"OpenAI stream rate limit: {exc}")
            yield '{"error": "Rate limit"}'
        except openai.APIError as exc:
            log.error(f"OpenAI stream API error: {exc}")
            yield f'{{"error": "{str(exc)[:100]}"}}'
        except Exception as exc:
            log.error(f"OpenAI stream error: {exc}")
            yield f'{{"error": "{str(exc)[:100]}"}}'

    # ═════════════════════════════════════════════════════════════
    # DB logging
    # ═════════════════════════════════════════════════════════════

    async def _log_message(
        self,
        session_id: str,
        system_prompt: str,
        user_prompt: str,
        response_text: str,
        tokens_in: int,
        tokens_out: int,
        cost_inr: float,
        duration_ms: int,
    ) -> None:
        """Log an LLM message to the database."""
        try:
            from storage.db import insert_llm_message
            await insert_llm_message({
                "session_id": session_id,
                "agent_name": "openai_client",
                "provider": "openai",
                "model": _MODEL,
                "direction": "request",
                "system_prompt": system_prompt[:500],
                "user_prompt": user_prompt[:500],
                "response_text": response_text[:2000],
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_inr": cost_inr,
                "duration_ms": duration_ms,
            })
        except Exception as exc:
            log.error(f"Failed to log LLM message: {exc}")


__all__ = ["OpenAIClient"]
