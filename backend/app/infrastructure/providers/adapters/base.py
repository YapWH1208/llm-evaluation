from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.db.models import ModelEndpoint
from app.infrastructure.providers.common import allowed_defaults, nonnegative_int
from app.infrastructure.providers.contracts import SandboxToolCall


SANDBOX_ECHO_TOOL_NAME = "sandbox_echo"
SANDBOX_ECHO_TOOL_DESCRIPTION = "Return the supplied message without executing any external action."
SANDBOX_ECHO_TOOL_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {"message": {"type": "string"}},
    "required": ["message"],
    "additionalProperties": False,
}


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
    max_output_token_path: tuple[str, ...] | None = None
    max_output_token_aliases: tuple[tuple[str, ...], ...] = ()
    reasoning_effort_path: tuple[str, ...] | None = None
    reasoning_effort_aliases: tuple[tuple[str, ...], ...] = ()
    sandbox_tool_calling_supported = False

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

    def build_sandbox_tool_request_with_options(
        self, endpoint: ModelEndpoint, messages: list[object], options: dict[str, object]
    ) -> ProviderRequest:
        return ProviderRequest(
            "POST", self.endpoint_url(endpoint), self.build_sandbox_tool_request(endpoint, messages, options)
        )

    def build_sandbox_tool_request(
        self, endpoint: ModelEndpoint, messages: list[object], options: dict[str, object]
    ) -> dict[str, Any]:
        raise ValueError(f"Tool-calling sandbox tests are not supported for {self.profile}.")

    def extract_sandbox_tool_calls(self, payload: dict[str, Any]) -> tuple[SandboxToolCall, ...]:
        raise ValueError(f"Tool-calling sandbox tests are not supported for {self.profile}.")

    def supports(self, capability_key: str) -> bool:
        return capability_key in self.capabilities

    def request_defaults(self) -> dict[str, object]:
        return {"max_tokens": 32, "temperature": 0}

    def endpoint_request_defaults(self, endpoint: ModelEndpoint) -> dict[str, object]:
        """Return endpoint defaults with typed settings translated for this provider."""

        raw_defaults = getattr(endpoint, "default_request_body", {})
        defaults = deepcopy(dict(raw_defaults)) if isinstance(raw_defaults, Mapping) else {}
        max_output_tokens = _endpoint_value(endpoint, "max_output_tokens")
        if isinstance(max_output_tokens, int) and not isinstance(max_output_tokens, bool):
            self._set_typed_default(
                defaults, self.max_output_token_path, self.max_output_token_aliases, max_output_tokens
            )
        reasoning_effort = _endpoint_value(endpoint, "reasoning_effort")
        if isinstance(reasoning_effort, str) and reasoning_effort:
            self._set_typed_default(
                defaults, self.reasoning_effort_path, self.reasoning_effort_aliases, reasoning_effort
            )
        return defaults

    def equivalent_request_field_groups(self) -> tuple[tuple[tuple[str, ...], ...], ...]:
        """Groups whose members mean the same option at different request layers."""

        return tuple(group for group in (self.max_output_token_aliases, self.reasoning_effort_aliases) if group)

    def connection_defaults(self, endpoint: ModelEndpoint) -> dict[str, Any]:
        """Return safe raw defaults without saved output limits for a bounded probe."""

        raw_defaults = getattr(endpoint, "default_request_body", {})
        defaults = self.safe_defaults(deepcopy(dict(raw_defaults)) if isinstance(raw_defaults, Mapping) else {})
        for path in self.max_output_token_aliases:
            _remove_path(defaults, path)
        return defaults

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

    @staticmethod
    def _set_typed_default(
        defaults: dict[str, object],
        path: tuple[str, ...] | None,
        aliases: tuple[tuple[str, ...], ...],
        value: object,
    ) -> None:
        if path is None:
            return
        for alias in aliases:
            _remove_path(defaults, alias)
        _set_path(defaults, path, value)


def _endpoint_value(endpoint: object, key: str) -> object | None:
    return getattr(endpoint, key, None)


def _set_path(target: dict[str, object], path: tuple[str, ...], value: object) -> None:
    current = target
    for key in path[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            child = {}
            current[key] = child
        current = child
    current[path[-1]] = value


def _remove_path(target: dict[str, object], path: tuple[str, ...]) -> None:
    current = target
    ancestors: list[tuple[dict[str, object], str]] = []
    for key in path[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            return
        ancestors.append((current, key))
        current = child
    current.pop(path[-1], None)
    for parent, key in reversed(ancestors):
        child = parent.get(key)
        if isinstance(child, dict) and not child:
            parent.pop(key, None)
