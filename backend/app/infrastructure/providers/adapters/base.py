from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.db.models import ModelEndpoint
from app.infrastructure.providers.common import allowed_defaults


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    method: str
    url: str
    body: dict[str, Any]


class ProviderAdapter(ABC):
    profile: str
    capabilities: frozenset[str] = frozenset()

    @property
    def allow_loopback(self) -> bool:
        return self.profile == "ollama_chat"

    def endpoint_url(self, endpoint: ModelEndpoint) -> str:
        suffix = self.path_suffix(endpoint)
        if suffix is None:
            return endpoint.base_url
        parsed = urlsplit(endpoint.base_url)
        return urlunsplit((parsed.scheme, parsed.netloc, f"{parsed.path.rstrip('/')}{suffix}", parsed.query, ""))

    @abstractmethod
    def path_suffix(self, endpoint: ModelEndpoint) -> str | None:
        ...

    @abstractmethod
    def build_request(self, endpoint: ModelEndpoint, messages: list[object], options: dict[str, object]) -> dict[str, Any]:
        ...

    @abstractmethod
    def build_connection_body(self, endpoint: ModelEndpoint) -> dict[str, object]:
        ...

    @abstractmethod
    def extract_prediction(self, payload: dict[str, Any]) -> str:
        ...

    def headers(self, endpoint: ModelEndpoint, api_key: str) -> dict[str, str]:
        headers = {str(name): str(value) for name, value in (endpoint.custom_headers or {}).items()}
        if self.profile == "anthropic_messages":
            headers["x-api-key"] = api_key
            headers.setdefault("anthropic-version", "2023-06-01")
        elif self.profile == "gemini_generate_content":
            headers["x-goog-api-key"] = api_key
        elif self.profile == "azure_openai_chat_completions":
            headers["api-key"] = api_key
        elif self.profile != "ollama_chat" or api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def build_request_with_options(self, endpoint: ModelEndpoint, messages: list[object], options: dict[str, object]) -> ProviderRequest:
        return ProviderRequest("POST", self.endpoint_url(endpoint), self.build_request(endpoint, messages, options))

    def supports(self, capability_key: str) -> bool:
        return capability_key in self.capabilities

    def safe_defaults(self, options: dict[str, object]) -> dict[str, Any]:
        return allowed_defaults(options)
