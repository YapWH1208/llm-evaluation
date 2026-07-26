from __future__ import annotations

import base64
import binascii
import ipaddress
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import perf_counter
from typing import Any, Protocol
from urllib.parse import urlparse, urlsplit, urlunsplit

import httpx

from app.db import ModelEndpoint
from app.services.content_ir import ContentValidationError, normalize_content_parts
from app.services.provider_headers import PROTECTED_REQUEST_FIELDS, provider_headers
from app.services.request_body import effective_request_options, request_snapshot_metadata


@dataclass(frozen=True, slots=True)
class SampleExecutionResult:
    success: bool
    request_snapshot: dict[str, Any]
    raw_response: str | None
    prediction: str | None
    error_type: str | None = None
    error_message: str | None = None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    retry_after_seconds: float | None = None


class ModelExecutor(Protocol):
    def execute(
        self,
        endpoint: ModelEndpoint,
        api_key: str,
        input_snapshot: dict[str, object],
    ) -> SampleExecutionResult: ...


class OpenAIChatCompletionsExecutor:
    """Executes a sample through one of the built-in provider protocol adapters."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport

    def execute(
        self,
        endpoint: ModelEndpoint,
        api_key: str,
        input_snapshot: dict[str, object],
    ) -> SampleExecutionResult:
        started_at = perf_counter()
        try:
            outbound_request = self._build_request(endpoint, input_snapshot)
            request_snapshot = _snapshot_with_request_evidence(outbound_request, input_snapshot)
        except ValueError as error:
            return SampleExecutionResult(
                False,
                {},
                None,
                None,
                "invalid_sample",
                str(error),
                latency_ms=_elapsed_ms(started_at),
            )
        try:
            with httpx.Client(
                timeout=endpoint.timeout_seconds,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                response = client.post(
                    _endpoint_url(endpoint),
                    headers=provider_headers(endpoint, api_key),
                    json=outbound_request,
                )
        except httpx.TimeoutException:
            return SampleExecutionResult(
                False,
                request_snapshot,
                None,
                None,
                "timeout",
                "Provider request timed out.",
                latency_ms=_elapsed_ms(started_at),
            )
        except httpx.RequestError:
            return SampleExecutionResult(
                False,
                request_snapshot,
                None,
                None,
                "connection_error",
                "Could not connect to the provider.",
                latency_ms=_elapsed_ms(started_at),
            )

        raw_response = response.text
        if response.is_error:
            return SampleExecutionResult(
                False,
                request_snapshot,
                raw_response,
                None,
                f"http_{response.status_code}",
                f"Provider returned HTTP {response.status_code}.",
                latency_ms=_elapsed_ms(started_at),
                retry_after_seconds=_parse_retry_after(response.headers.get("retry-after")),
            )

        try:
            payload = response.json()
            prediction = _extract_prediction(payload, _protocol_profile(endpoint))
            input_tokens, output_tokens = _extract_usage(payload)
        except (IndexError, KeyError, TypeError, ValueError):
            return SampleExecutionResult(
                False,
                request_snapshot,
                raw_response,
                None,
                "response_parse_error",
                "Provider returned an unexpected response payload.",
                latency_ms=_elapsed_ms(started_at),
            )

        if not isinstance(prediction, str):
            return SampleExecutionResult(
                False,
                request_snapshot,
                raw_response,
                None,
                "response_parse_error",
                "Provider response did not contain text content.",
                latency_ms=_elapsed_ms(started_at),
            )

        return SampleExecutionResult(
            True,
            request_snapshot,
            raw_response,
            prediction,
            latency_ms=_elapsed_ms(started_at),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    @staticmethod
    def _build_request(
        endpoint: ModelEndpoint,
        input_snapshot: dict[str, object],
    ) -> dict[str, Any]:
        messages = input_snapshot.get("messages")
        if not isinstance(messages, list):
            raise ValueError("Text sample input must contain a messages list.")
        protocol_profile = _protocol_profile(endpoint)
        request_options = effective_request_options(
            input_snapshot,
            protocol_profile=protocol_profile,
            model_defaults=endpoint.default_request_body,
        )
        if protocol_profile == "openai_chat_completions":
            return _build_chat_request(endpoint, messages, request_options)
        if protocol_profile == "openai_responses":
            return _build_responses_request(endpoint, messages, request_options)
        if protocol_profile == "anthropic_messages":
            return _build_anthropic_request(endpoint, messages, request_options)
        if protocol_profile == "gemini_generate_content":
            return _build_gemini_request(endpoint, messages, request_options)
        if protocol_profile == "ollama_chat":
            return _build_ollama_request(endpoint, messages, request_options)
        if protocol_profile in {"azure_openai_chat_completions", "custom_http_json"}:
            return _build_chat_request(endpoint, messages, request_options)
        raise ValueError(f"Unsupported execution protocol profile: {protocol_profile}.")

def _protocol_profile(endpoint: ModelEndpoint) -> str:
    return str(getattr(endpoint, "protocol_profile", None) or "openai_chat_completions")


def _endpoint_url(endpoint: ModelEndpoint) -> str:
    profile = _protocol_profile(endpoint)
    if profile == "custom_http_json":
        return endpoint.base_url
    if profile == "anthropic_messages":
        suffix = "/v1/messages"
    elif profile == "gemini_generate_content":
        suffix = f"/models/{endpoint.model_name}:generateContent"
    elif profile == "ollama_chat":
        suffix = "/api/chat"
    elif profile == "openai_responses":
        suffix = "/responses"
    else:
        suffix = "/chat/completions"
    parsed = urlsplit(endpoint.base_url)
    return urlunsplit((parsed.scheme, parsed.netloc, f"{parsed.path.rstrip('/')}{suffix}", parsed.query, ""))


def _allowed_defaults(defaults: dict[str, object]) -> dict[str, Any]:
    return {
        key: value
        for key, value in defaults.items()
        if key not in PROTECTED_REQUEST_FIELDS
    }


def _build_chat_request(
    endpoint: ModelEndpoint,
    messages: list[object],
    request_options: dict[str, object],
) -> dict[str, Any]:
    return {
        **_allowed_defaults(request_options),
        "model": endpoint.model_name,
        "messages": _translate_messages(messages),
        "stream": False,
    }


def _build_responses_request(
    endpoint: ModelEndpoint,
    messages: list[object],
    request_options: dict[str, object],
) -> dict[str, Any]:
    return {
        **_allowed_defaults(request_options),
        "model": endpoint.model_name,
        "input": _translate_responses_messages(messages),
        "stream": False,
        "store": False,
    }


def _build_anthropic_request(
    endpoint: ModelEndpoint,
    messages: list[object],
    request_options: dict[str, object],
) -> dict[str, Any]:
    allowed = _allowed_defaults(request_options)
    system_parts: list[dict[str, object]] = []
    translated: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object.")
        role = message.get("role")
        content = _translate_anthropic_content(message.get("content"))
        if role in {"system", "developer"}:
            system_parts.extend(content)
        elif role in {"user", "assistant"}:
            translated.append({"role": role, "content": content})
        else:
            raise ValueError("Anthropic Messages supports system, user, and assistant messages only.")
    max_tokens = allowed.pop("max_tokens", allowed.pop("max_output_tokens", 32))
    request: dict[str, Any] = {
        **allowed,
        "model": endpoint.model_name,
        "messages": translated,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if system_parts:
        request["system"] = system_parts
    return request


def _build_gemini_request(
    endpoint: ModelEndpoint,
    messages: list[object],
    request_options: dict[str, object],
) -> dict[str, Any]:
    allowed = _allowed_defaults(request_options)
    contents: list[dict[str, object]] = []
    system_parts: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object.")
        role = message.get("role")
        parts = _translate_gemini_content(message.get("content"))
        if role in {"system", "developer"}:
            system_parts.extend(parts)
        elif role == "assistant":
            contents.append({"role": "model", "parts": parts})
        elif role == "user":
            contents.append({"role": "user", "parts": parts})
        else:
            raise ValueError("Gemini GenerateContent supports system, user, and assistant messages only.")
    generation_config = dict(allowed.pop("generationConfig", {})) if isinstance(allowed.get("generationConfig"), dict) else {}
    option_map = {"max_tokens": "maxOutputTokens", "max_output_tokens": "maxOutputTokens", "top_p": "topP", "top_k": "topK"}
    for source, target in option_map.items():
        if source in allowed:
            generation_config[target] = allowed.pop(source)
    if "temperature" in allowed:
        generation_config["temperature"] = allowed.pop("temperature")
    request: dict[str, Any] = {**allowed, "contents": contents}
    if system_parts:
        request["systemInstruction"] = {"parts": system_parts}
    if generation_config:
        request["generationConfig"] = generation_config
    return request


def _build_ollama_request(
    endpoint: ModelEndpoint,
    messages: list[object],
    request_options: dict[str, object],
) -> dict[str, Any]:
    allowed = _allowed_defaults(request_options)
    options = dict(allowed.pop("options", {})) if isinstance(allowed.get("options"), dict) else {}
    option_map = {"max_tokens": "num_predict", "max_output_tokens": "num_predict", "top_p": "top_p", "top_k": "top_k", "temperature": "temperature", "seed": "seed"}
    for source, target in option_map.items():
        if source in allowed:
            options[target] = allowed.pop(source)
    request: dict[str, Any] = {
        **allowed,
        "model": endpoint.model_name,
        "messages": _translate_ollama_messages(messages),
        "stream": False,
    }
    if options:
        request["options"] = options
    return request


def _snapshot_with_request_evidence(
    outbound_request: dict[str, Any],
    input_snapshot: dict[str, object],
) -> dict[str, Any]:
    """Persist provider request and locally generated merge evidence separately."""

    snapshot = dict(outbound_request)
    evidence = request_snapshot_metadata(input_snapshot)
    if evidence is not None:
        snapshot["_evaluation"] = {"request_body_evidence": evidence}
    return snapshot


def _extract_prediction(payload: dict[str, Any], protocol_profile: str) -> str:
    if protocol_profile in {"openai_chat_completions", "azure_openai_chat_completions"}:
        prediction = payload["choices"][0]["message"]["content"]
        if not isinstance(prediction, str):
            raise ValueError("Chat Completions response did not contain text content.")
        return prediction
    if protocol_profile == "openai_responses":
        output_text = payload.get("output_text")
        if isinstance(output_text, str):
            return output_text
        fragments: list[str] = []
        output = payload.get("output")
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict) or item.get("type") != "message":
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                        fragments.append(part["text"])
        if fragments:
            return "".join(fragments)
        raise ValueError("Responses API response did not contain output text.")
    if protocol_profile == "anthropic_messages":
        content = payload.get("content")
        if isinstance(content, list):
            fragments = [part["text"] for part in content if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)]
            if fragments:
                return "".join(fragments)
        raise ValueError("Anthropic response did not contain text content.")
    if protocol_profile == "gemini_generate_content":
        candidates = payload.get("candidates")
        if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict):
            content = candidates[0].get("content")
            parts = content.get("parts") if isinstance(content, dict) else None
            if isinstance(parts, list):
                fragments = [part["text"] for part in parts if isinstance(part, dict) and isinstance(part.get("text"), str)]
                if fragments:
                    return "".join(fragments)
        raise ValueError("Gemini response did not contain text content.")
    if protocol_profile == "ollama_chat":
        message = payload.get("message")
        prediction = message.get("content") if isinstance(message, dict) else None
        if isinstance(prediction, str):
            return prediction
        raise ValueError("Ollama response did not contain text content.")
    for candidate in (
        payload.get("output_text"),
        payload.get("text"),
        payload.get("response"),
        payload.get("prediction"),
    ):
        if isinstance(candidate, str):
            return candidate
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        prediction = message.get("content") if isinstance(message, dict) else None
        if isinstance(prediction, str):
            return prediction
    raise ValueError("Custom JSON response did not contain text content.")


def _translate_anthropic_content(content: object) -> list[dict[str, object]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    parts = _normalized_content_parts(content)
    translated: list[dict[str, object]] = []
    for part in parts:
        if part["type"] == "text":
            translated.append({"type": "text", "text": part["text"]})
        elif part["type"] == "image":
            source = part["source"]
            if not isinstance(source, dict):
                raise ValueError("Anthropic image content requires a source object.")
            if isinstance(source.get("base64_data"), str):
                _validate_base64(source["base64_data"])
                translated.append({"type": "image", "source": {"type": "base64", "media_type": part["mime_type"], "data": source["base64_data"]}})
            elif isinstance(source.get("url"), str):
                _validate_remote_media_url(source["url"])
                translated.append({"type": "image", "source": {"type": "url", "url": source["url"]}})
            else:
                raise ValueError("Anthropic image content requires base64_data or a remote URL.")
        else:
            raise ValueError(f"Anthropic Messages does not support {part['type']} content through this adapter.")
    return translated


def _translate_gemini_content(content: object) -> list[dict[str, object]]:
    if isinstance(content, str):
        return [{"text": content}]
    parts = _normalized_content_parts(content)
    translated: list[dict[str, object]] = []
    for part in parts:
        if part["type"] == "text":
            translated.append({"text": part["text"]})
            continue
        source = part["source"]
        encoded = source.get("base64_data") if isinstance(source, dict) else None
        if not isinstance(encoded, str):
            raise ValueError(f"Gemini {part['type']} content requires base64_data through this adapter.")
        _validate_base64(encoded)
        translated.append({"inlineData": {"mimeType": part["mime_type"], "data": encoded}})
    return translated


def _translate_ollama_messages(messages: list[object]) -> list[dict[str, object]]:
    translated: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object.")
        role = message.get("role")
        if role not in {"system", "user", "assistant"}:
            raise ValueError("Ollama Chat supports system, user, and assistant messages only.")
        content = message.get("content")
        if isinstance(content, str):
            translated.append({"role": role, "content": content})
            continue
        parts = _normalized_content_parts(content)
        text = "".join(part["text"] for part in parts if part["type"] == "text")
        images: list[str] = []
        for part in parts:
            if part["type"] == "text":
                continue
            if part["type"] != "image":
                raise ValueError(f"Ollama Chat does not support {part['type']} content through this adapter.")
            source = part["source"]
            encoded = source.get("base64_data") if isinstance(source, dict) else None
            if not isinstance(encoded, str):
                raise ValueError("Ollama image content requires base64_data through this adapter.")
            _validate_base64(encoded)
            images.append(encoded)
        rendered: dict[str, object] = {"role": role, "content": text}
        if images:
            rendered["images"] = images
        translated.append(rendered)
    return translated


def _normalized_content_parts(content: object) -> list[dict[str, Any]]:
    if not isinstance(content, list):
        raise ValueError("Message content must be text or a list of content parts.")
    try:
        parts = normalize_content_parts(content)
    except ContentValidationError as error:
        raise ValueError(str(error)) from error
    if any(part["type"] == "tool_result" for part in parts):
        raise ValueError("This protocol adapter does not support tool results.")
    return parts


def _translate_responses_messages(messages: list[object]) -> list[dict[str, object]]:
    translated: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object.")
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant", "system", "developer"}:
            raise ValueError("Responses API messages require a user, assistant, system, or developer role.")
        if isinstance(content, str):
            parts = [{"type": "input_text", "text": content}]
            tool_results: list[dict[str, object]] = []
        elif isinstance(content, list):
            try:
                normalized = normalize_content_parts(content)
            except ContentValidationError as error:
                raise ValueError(str(error)) from error
            parts = [_translate_responses_content_part(part) for part in normalized if part["type"] != "tool_result"]
            tool_results = [{"type": "function_call_output", "call_id": part["tool_call_id"], "output": part["content"]} for part in normalized if part["type"] == "tool_result"]
        else:
            raise ValueError("Message content must be text or a list of content parts.")
        if parts:
            translated.append({"role": role, "content": parts})
        translated.extend(tool_results)
    return translated


def _translate_responses_content_part(part: dict[str, Any]) -> dict[str, object]:
    part_type = part["type"]
    if part_type == "text":
        return {"type": "input_text", "text": part["text"]}
    if part_type == "image":
        return {"type": "input_image", "image_url": _source_as_data_or_remote_url(part)}
    if part_type == "audio":
        source = part["source"]
        encoded = source.get("base64_data") if isinstance(source, dict) else None
        if not isinstance(encoded, str):
            raise ValueError("Responses API audio content requires base64_data.")
        _validate_base64(encoded)
        audio_format = part["mime_type"].split("/", 1)[1]
        if audio_format == "mpeg":
            audio_format = "mp3"
        if audio_format not in {"wav", "mp3"}:
            raise ValueError("Responses API audio supports WAV or MP3 content only.")
        return {"type": "input_audio", "input_audio": {"data": encoded, "format": audio_format}}
    if part_type in {"file", "video"}:
        source = part["source"]
        if not isinstance(source, dict):
            raise ValueError("File and video content parts require a source object.")
        filename = "input-video" if part_type == "video" else "input-file"
        if isinstance(source.get("url"), str):
            _validate_remote_media_url(source["url"])
            return {"type": "input_file", "file_url": source["url"], "filename": filename}
        if isinstance(source.get("base64_data"), str):
            _validate_base64(source["base64_data"])
            return {"type": "input_file", "file_data": source["base64_data"], "filename": filename}
        raise ValueError("Responses API file and video content requires base64_data or a remote URL.")
    raise ValueError(f"Responses API does not support {part_type} content through this adapter.")


def normalize_exact_match(value: str) -> str:
    return " ".join(value.strip().split())


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)


def _extract_usage(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    usage = payload.get("usage")
    if isinstance(usage, dict):
        input_value = usage.get("prompt_tokens", usage.get("input_tokens"))
        output_value = usage.get("completion_tokens", usage.get("output_tokens"))
        return _nonnegative_int(input_value), _nonnegative_int(output_value)
    usage_metadata = payload.get("usageMetadata")
    if isinstance(usage_metadata, dict):
        return _nonnegative_int(usage_metadata.get("promptTokenCount")), _nonnegative_int(usage_metadata.get("candidatesTokenCount"))
    input_value = payload.get("prompt_eval_count")
    output_value = payload.get("eval_count")
    return _nonnegative_int(input_value), _nonnegative_int(output_value)


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _parse_retry_after(value: str | None, now: datetime | None = None) -> float | None:
    """Return a non-negative Retry-After delay from a provider response header."""

    if not value:
        return None
    try:
        delay = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        delay = (retry_at - (now or datetime.now(timezone.utc))).total_seconds()
    return max(0.0, delay)


def _translate_messages(messages: list[object]) -> list[dict[str, object]]:
    translated: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object.")
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or not role:
            raise ValueError("Each message must include a role.")
        if isinstance(content, str):
            translated.append({"role": role, "content": content})
            continue
        if not isinstance(content, list):
            raise ValueError("Message content must be text or a list of content parts.")
        try:
            parts = normalize_content_parts(content)
        except ContentValidationError as error:
            raise ValueError(str(error)) from error
        tool_results = [part for part in parts if part["type"] == "tool_result"]
        if tool_results:
            if len(parts) != 1 or role != "tool":
                raise ValueError("Chat Completions tool results must be a standalone message with role tool.")
            translated.append({"role": "tool", "tool_call_id": tool_results[0]["tool_call_id"], "content": tool_results[0]["content"]})
            continue
        translated.append({"role": role, "content": [_translate_content_part(part) for part in parts]})
    return translated


def _translate_content_part(part: dict[str, Any]) -> dict[str, object]:
    part_type = part["type"]
    if part_type == "text":
        return {"type": "text", "text": part["text"]}
    if part_type == "image":
        return {"type": "image_url", "image_url": {"url": _source_as_data_or_remote_url(part)}}
    if part_type == "audio":
        source = part["source"]
        encoded = source.get("base64_data") if isinstance(source, dict) else None
        if not isinstance(encoded, str):
            raise ValueError("OpenAI Chat Completions audio content requires base64_data.")
        _validate_base64(encoded)
        audio_format = part["mime_type"].split("/", 1)[1]
        if audio_format == "mpeg":
            audio_format = "mp3"
        if audio_format not in {"wav", "mp3"}:
            raise ValueError("OpenAI Chat Completions audio supports WAV or MP3 content only.")
        return {"type": "input_audio", "input_audio": {"data": encoded, "format": audio_format}}
    raise ValueError(
        f"OpenAI Chat Completions does not support {part_type} content through this adapter. "
        "Use a compatible protocol adapter for video or file inputs."
    )


def _source_as_data_or_remote_url(part: dict[str, Any]) -> str:
    source = part["source"]
    if not isinstance(source, dict):
        raise ValueError("Media content parts require a source object.")
    remote_url = source.get("url")
    if isinstance(remote_url, str):
        _validate_remote_media_url(remote_url)
        return remote_url
    encoded = source.get("base64_data")
    if isinstance(encoded, str):
        _validate_base64(encoded)
        return f"data:{part['mime_type']};base64,{encoded}"
    if source.get("asset_id"):
        raise ValueError("Stored media assets must be resolved to base64_data or a remote URL before execution.")
    raise ValueError("Media content part has no usable provider source.")


def _validate_base64(value: str) -> None:
    try:
        base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Media base64_data must be valid base64.") from error


def _validate_remote_media_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Remote media URLs must be absolute HTTP or HTTPS URLs.")
    host = parsed.hostname
    if host is None:
        raise ValueError("Remote media URL host is missing.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
        raise ValueError("Remote media URLs must not target private or local IP addresses.")
