"""
TradeOS India — Abstract base class for all LLM providers.

All LLM clients must implement complete(), stream(), and expose
model_name, provider, and cost_per_1k_tokens_inr properties.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator


class BaseLLM(ABC):
    """Abstract base for LLM provider clients.

    Every provider (Claude, OpenAI, Groq) implements this interface.
    All calls are async to avoid blocking the Qt main thread.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier string."""
        ...

    @property
    @abstractmethod
    def provider(self) -> str:
        """Return the provider name (e.g. 'claude', 'openai', 'groq')."""
        ...

    @property
    @abstractmethod
    def cost_per_1k_tokens_inr(self) -> float:
        """Return the approximate cost per 1000 tokens in INR."""
        ...

    @abstractmethod
    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1000,
    ) -> str:
        """Send a completion request and return the full response text.

        Args:
            system: System prompt.
            user: User message.
            max_tokens: Maximum tokens in the response.

        Returns:
            The assistant's response text.
        """
        ...

    @abstractmethod
    async def stream(
        self,
        system: str,
        user: str,
    ) -> AsyncIterator[str]:
        """Send a streaming request and yield response chunks.

        Args:
            system: System prompt.
            user: User message.

        Yields:
            Text chunks as they arrive.
        """
        ...


__all__ = ["BaseLLM"]
