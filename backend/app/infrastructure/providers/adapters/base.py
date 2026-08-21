from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.db.models import ModelEndpoint
from app.infrastructure.providers.common import allowed_defaults, nonnegative_int


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    method: str
    url: str
    body: dict[str, Any]


class ProviderAdapter(ABC):
    profile: str
    capabilities: frozenset[str] = frozenset()
    allow_loopback = False
    credential_header = "Authorization"
    credential_prefix = "Bearer "
    omit_empty_credential = False
    static_headers: dict[str, str] = {}
    output_token_option = "max_tokens"

    def endpoint_url(self, endpoint: ModelEndpoint) -> str:
        suffix = self.path_suffix(endpoint)
        if suffix is None:
            return endpoint.base_url
        parsed = urlsplit(endpoint.base_url)
        return urlunsplit((parsed.scheme, parsed.netloc, f"{parsed.path.rstrip('/')}{suffix}", parsed.query, ""))

    @abstractmethod
    def path_suffix(self, endpoint: ModelEndpoint) -> str | None: ...

    @abstractmethod
    def build_request(
        self, endpoint: ModelEndpoint, messages: list[object], options: dict[str, object]
    ) -> dict[str, Any]: ...

    @abstractmethod
    def build_connection_body(self, endpoint: ModelEndpoint) -> dict[str, object]: ...

    @abstractmethod
    def extract_prediction(self, payload: dict[str, Any]) -> str: ...

    def headers(self, endpoint: ModelEndpoint, api_key: str) -> dict[str, str]:
        headers = {str(name): str(value) for name, value in (endpoint.custom_headers or {}).items()}
        if api_key or not self.omit_empty_credential:
            headers[self.credential_header] = f"{self.credential_prefix}{api_key}"
        for name, value in self.static_headers.items():
            headers.setdefault(name, value)
        return headers

    def build_request_with_options(
        self, endpoint: ModelEndpoint, messages: list[object], options: dict[str, object]
    ) -> ProviderRequest:
        return ProviderRequest("POST", self.endpoint_url(endpoint), self.build_request(endpoint, messages, options))

    def supports(self, capability_key: str) -> bool:
        return capability_key in self.capabilities

    def request_defaults(self) -> dict[str, object]:
        return {"max_tokens": 32, "temperature": 0}

    def capability_probe_options(self) -> dict[str, object]:
        return {"temperature": 0, self.output_token_option: 8}

    def extract_usage(self, payload: dict[str, Any]) -> tuple[int | None, int | None]:
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            return None, None
        return nonnegative_int(usage.get("prompt_tokens", usage.get("input_tokens"))), nonnegative_int(
            usage.get("completion_tokens", usage.get("output_tokens"))
        )

    def extract_token_logprobs(self, payload: dict[str, Any]) -> tuple[float, ...] | None:
        return None

    def safe_defaults(self, options: dict[str, object]) -> dict[str, Any]:
        return allowed_defaults(options)
