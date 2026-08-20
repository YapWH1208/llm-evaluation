from __future__ import annotations

from collections.abc import Iterable

from app.db.models import ModelEndpoint
from app.infrastructure.providers.adapters import (
    AnthropicMessagesAdapter,
    AzureOpenAIChatAdapter,
    CustomHttpJsonAdapter,
    GeminiGenerateContentAdapter,
    OllamaChatAdapter,
    OpenAIChatCompletionsAdapter,
    OpenAIResponsesAdapter,
)
from app.infrastructure.providers.adapters.base import ProviderAdapter
from app.infrastructure.providers.errors import UnsupportedProviderProfileError


class ProviderRegistry:
    """Composition-bound registry for all supported provider protocols."""

    def __init__(self, adapters: Iterable[ProviderAdapter] | None = None) -> None:
        configured = tuple(adapters or (
            OpenAIChatCompletionsAdapter(),
            OpenAIResponsesAdapter(),
            AnthropicMessagesAdapter(),
            GeminiGenerateContentAdapter(),
            AzureOpenAIChatAdapter(),
            OllamaChatAdapter(),
            CustomHttpJsonAdapter(),
        ))
        self._adapters = {adapter.profile: adapter for adapter in configured}

    @property
    def profiles(self) -> frozenset[str]:
        return frozenset(self._adapters)

    def for_endpoint(self, endpoint: ModelEndpoint) -> ProviderAdapter:
        profile = str(getattr(endpoint, "protocol_profile", None) or "openai_chat_completions")
        return self.for_profile(profile)

    def for_profile(self, profile: str) -> ProviderAdapter:
        try:
            return self._adapters[profile]
        except KeyError as error:
            raise UnsupportedProviderProfileError(f"Unsupported provider protocol profile: {profile}.") from error
