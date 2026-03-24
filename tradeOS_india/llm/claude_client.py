"""
TradeOS India — Claude (Anthropic) LLM client.

Uses claude-sonnet-4-6 via the anthropic SDK. Token loaded from
OS keyring. Retries with exponential backoff on rate limit and API errors.
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

log = get_logger("llm.claude_client")

_MODEL = "claude-sonnet-4-6"
_KEYRING_KEY = "tradeOS_claude_token"
_COST_PER_1K_INR = 0.9
_MAX_RETRIES = 3
_INITIAL_BACKOFF_S = 1.0


class ClaudeClient(BaseLLM):
    """Anthropic Claude LLM client.

    Loads API token from OS keyring, uses claude-sonnet-4-6,
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
        """Return the Claude model identifier."""
        return _MODEL

    @property
    def provider(self) -> str:
        """Return the provider name."""
        return "claude"

    @property
    def cost_per_1k_tokens_inr(self) -> float:
        """Return cost per 1K tokens in INR."""
        return _COST_PER_1K_INR

    # ═════════════════════════════════════════════════════════════
    # Initialization
    # ═════════════════════════════════════════════════════════════

    def _ensure_client(self) -> bool:
        """Initialize the Anthropic client if not already done.

        Returns:
            True if client is ready.
        """
        if self._client is not None:
            return True

        self._api_key = get_secret(_KEYRING_KEY) or ""
        if not self._api_key:
            log.warning("Claude API key not found in keyring")
            return False

        try:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
            log.info("Claude client initialized")
            return True
        except ImportError:
            log.error("anthropic SDK not installed")
            return False
        except Exception as exc:
            log.error(f"Failed to init Claude client: {exc}")
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
        """Send a completion request to Claude.

        Retries up to 3 times with exponential backoff on transient errors.

        Args:
            system: System prompt.
            user: User message.
            max_tokens: Max response tokens.

        Returns:
            Response text string.
        """
        if not self._ensure_client():
            return '{"error": "Claude client not initialized"}'

        session_id = uuid.uuid4().hex[:12]
        start_ms = time.monotonic()
        backoff = _INITIAL_BACKOFF_S

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                import anthropic

                response = await self._client.messages.create(
                    model=_MODEL,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )

                text = response.content[0].text if response.content else ""
                tokens_in = response.usage.input_tokens
                tokens_out = response.usage.output_tokens
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

                # Log to DB (fire and forget)
                await self._log_message(
                    session_id=session_id,
                    direction="request",
                    system_prompt=system,
                    user_prompt=user,
                    response_text=text,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_inr=cost_inr,
                    duration_ms=duration_ms,
                )

                log.debug(
                    f"Claude complete: {tokens_in}+{tokens_out} tokens, "
                    f"{duration_ms}ms, INR {cost_inr:.2f}"
                )
                return text

            except anthropic.RateLimitError as exc:
                log.warning(
                    f"Claude rate limit (attempt {attempt}/{_MAX_RETRIES}): {exc}"
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    return '{"error": "Rate limit exceeded after retries"}'

            except anthropic.APIError as exc:
                log.error(
                    f"Claude API error (attempt {attempt}/{_MAX_RETRIES}): {exc}"
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    return f'{{"error": "API error: {str(exc)[:100]}"}}'

            except Exception as exc:
                log.error(f"Claude unexpected error: {exc}")
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
        """Stream a response from Claude, yielding text chunks.

        Args:
            system: System prompt.
            user: User message.

        Yields:
            Text chunks as they arrive.
        """
        if not self._ensure_client():
            yield '{"error": "Claude client not initialized"}'
            return

        try:
            import anthropic

            async with self._client.messages.stream(
                model=_MODEL,
                max_tokens=2000,
                system=system,
                messages=[{"role": "user", "content": user}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text

        except anthropic.RateLimitError as exc:
            log.warning(f"Claude stream rate limit: {exc}")
            yield '{"error": "Rate limit"}'
        except anthropic.APIError as exc:
            log.error(f"Claude stream API error: {exc}")
            yield f'{{"error": "{str(exc)[:100]}"}}'
        except Exception as exc:
            log.error(f"Claude stream error: {exc}")
            yield f'{{"error": "{str(exc)[:100]}"}}'

    # ═════════════════════════════════════════════════════════════
    # DB logging
    # ═════════════════════════════════════════════════════════════

    async def _log_message(
        self,
        session_id: str,
        direction: str,
        system_prompt: str,
        user_prompt: str,
        response_text: str,
        tokens_in: int,
        tokens_out: int,
        cost_inr: float,
        duration_ms: int,
    ) -> None:
        """Log an LLM message to the database.

        Args:
            session_id: Session identifier.
            direction: 'request' or 'response'.
            system_prompt: System prompt used.
            user_prompt: User message sent.
            response_text: Model response.
            tokens_in: Input token count.
            tokens_out: Output token count.
            cost_inr: Cost in INR.
            duration_ms: Duration in milliseconds.
        """
        try:
            from storage.db import insert_llm_message
            await insert_llm_message({
                "session_id": session_id,
                "agent_name": "claude_client",
                "provider": "claude",
                "model": _MODEL,
                "direction": direction,
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


__all__ = ["ClaudeClient"]
