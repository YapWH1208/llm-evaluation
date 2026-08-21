from pathlib import Path
import json

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app
from app.db.models import CapabilityDetection
from app.infrastructure.providers.capabilities import DEFAULT_CAPABILITY_KEYS, ProviderCapabilityDetector
from app.infrastructure.providers.contracts import CapabilityDetectionResult
from app.db.models import ModelEndpoint


@pytest.fixture(autouse=True)
def public_provider_dns(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.network.outbound.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )


def test_capabilities_keep_user_declaration_separate(tmp_path: Path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", secret_encryption_key=Fernet.generate_key().decode()
        )
    )
    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "m"},
        ).json()
        response = client.put(
            f"/api/v1/model-endpoints/{endpoint['id']}/capabilities",
            json={"capability_key": "text_input", "user_declared_status": "supported"},
        )
        assert response.status_code == 200
        assert response.json()["effective_status"] == "user_verified"
        listed = client.get(f"/api/v1/model-endpoints/{endpoint['id']}/capabilities")
        assert listed.json()[0]["auto_detection_status"] == "not_tested"


def test_capability_detection_records_safe_evidence_without_overwriting_user_declaration(tmp_path: Path) -> None:
    class Detector:
        def detect(self, endpoint, api_key: str, capability_keys: list[str]):
            assert endpoint.model_name == "m"
            assert api_key == "secret"
            assert capability_keys == ["text_input", "image_input"]
            return [
                CapabilityDetectionResult(
                    "text_input", CapabilityDetection.PASSED, {"adapter_version": "test/1", "outcome": "passed"}
                ),
                CapabilityDetectionResult(
                    "image_input",
                    CapabilityDetection.UNSUPPORTED_BY_ADAPTER,
                    {"adapter_version": "test/1", "outcome": "not_run"},
                ),
            ]

    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", secret_encryption_key=Fernet.generate_key().decode()
        ),
        capability_detector=Detector(),
    )
    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "m"},
        ).json()
        client.put(
            f"/api/v1/model-endpoints/{endpoint['id']}/capabilities",
            json={"capability_key": "text_input", "user_declared_status": "supported"},
        )
        response = client.post(
            f"/api/v1/model-endpoints/{endpoint['id']}/capabilities/detect",
            json={"capability_keys": ["text_input", "image_input"]},
        )
        assert response.status_code == 200
        detected = {item["capability_key"]: item for item in response.json()}
        assert detected["text_input"]["user_declared_status"] == "supported"
        assert detected["text_input"]["auto_detection_status"] == "passed"
        assert detected["text_input"]["effective_status"] == "verified_by_both"
        assert detected["text_input"]["detection_evidence"] == {"adapter_version": "test/1", "outcome": "passed"}
        assert detected["image_input"]["auto_detection_status"] == "unsupported_by_adapter"


def test_capability_conflicts_are_directly_queryable_with_resolution_options(tmp_path: Path) -> None:
    class Detector:
        def detect(self, endpoint, api_key: str, capability_keys: list[str]):
            return [
                CapabilityDetectionResult(
                    key, CapabilityDetection.FAILED, {"adapter_version": "test/1", "outcome": "failed"}
                )
                for key in capability_keys
            ]

    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", secret_encryption_key=Fernet.generate_key().decode()
        ),
        capability_detector=Detector(),
    )
    with TestClient(app) as client:
        endpoint = client.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "m"},
        ).json()
        client.put(
            f"/api/v1/model-endpoints/{endpoint['id']}/capabilities",
            json={"capability_key": "text_input", "user_declared_status": "supported"},
        )
        assert (
            client.post(
                f"/api/v1/model-endpoints/{endpoint['id']}/capabilities/detect",
                json={"capability_keys": ["text_input"]},
            ).status_code
            == 200
        )
        conflicts = client.get(f"/api/v1/model-endpoints/{endpoint['id']}/capabilities/conflicts")
        assert conflicts.status_code == 200
        assert conflicts.json()[0]["effective_status"] == "user_declared_detection_failed"
        assert conflicts.json()[0]["resolution_options"] == ["keep_disabled", "force_enable", "redetect"]


def test_openai_detector_probes_image_and_audio_and_marks_video_adapter_unsupported() -> None:
    observed: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "OK"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
        )

    endpoint = ModelEndpoint(
        display_name="test",
        base_url="https://models.example.test/v1",
        model_name="m",
        encrypted_api_key="unused",
        api_key_mask="****test",
    )
    results = ProviderCapabilityDetector(transport=httpx.MockTransport(handler)).detect(
        endpoint, "secret", ["image_input", "audio_input", "video_input"]
    )
    by_key = {result.capability_key: result for result in results}
    assert by_key["image_input"].status == CapabilityDetection.PASSED
    assert by_key["audio_input"].status == CapabilityDetection.PASSED
    assert by_key["video_input"].status == CapabilityDetection.UNSUPPORTED_BY_ADAPTER
    assert observed[0]["messages"][0]["content"][1]["type"] == "image_url"
    assert observed[1]["messages"][0]["content"][1]["type"] == "input_audio"


def test_capability_catalog_includes_all_declared_modalities_outputs_and_context_fields() -> None:
    assert {
        "multiple_images",
        "multiple_audio_files",
        "multiple_videos",
        "mixed_media_input",
        "text_output",
        "image_output",
        "audio_output",
        "video_output",
        "file_output",
        "maximum_context_length",
        "maximum_output_length",
        "supported_mime_types",
        "supported_languages",
    }.issubset(DEFAULT_CAPABILITY_KEYS)


def test_openai_detector_uses_minimal_multi_image_probe_and_accepts_sse_streaming() -> None:
    observed: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        observed.append(body)
        if body.get("stream"):
            return httpx.Response(
                200, content='data: {"choices": []}\n\n', headers={"content-type": "text/event-stream"}
            )
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    endpoint = ModelEndpoint(
        display_name="test",
        base_url="https://models.example.test/v1",
        model_name="m",
        encrypted_api_key="unused",
        api_key_mask="****test",
    )
    results = ProviderCapabilityDetector(transport=httpx.MockTransport(handler)).detect(
        endpoint, "secret", ["multiple_images", "streaming"]
    )
    assert {item.capability_key for item in results if item.status == CapabilityDetection.PASSED} == {
        "multiple_images",
        "streaming",
    }
    assert [part["type"] for part in observed[0]["messages"][0]["content"]] == ["text", "image_url", "image_url"]
    evidence = {item.capability_key: item.evidence for item in results}
    assert evidence["multiple_images"]["request_summary"] == {
        "capability": "multiple_images",
        "message_count": 1,
        "content_types": ["text", "image", "image"],
        "request_fields": ["max_tokens", "model", "stream", "temperature"],
    }
    assert "base64" not in json.dumps(evidence)


def test_openai_detector_uses_platform_owned_advanced_capability_probes() -> None:
    observed: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "OK"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
        )

    endpoint = ModelEndpoint(
        display_name="test",
        base_url="https://models.example.test/v1",
        model_name="m",
        encrypted_api_key="unused",
        api_key_mask="****test",
    )
    keys = [
        "tool_calling",
        "parallel_tool_calling",
        "structured_output",
        "json_mode",
        "multi_turn_conversation",
        "streaming",
        "seed",
        "logprobs",
    ]
    results = ProviderCapabilityDetector(transport=httpx.MockTransport(handler)).detect(endpoint, "secret", keys)
    assert {result.capability_key for result in results if result.status == CapabilityDetection.PASSED} == set(keys)
    assert observed[0]["tools"][0]["function"]["name"] == "probe"
    assert observed[1]["parallel_tool_calls"] is True
    assert observed[2]["response_format"]["type"] == "json_schema"
    assert observed[3]["response_format"] == {"type": "json_object"}
    assert len(observed[4]["messages"]) == 3
    assert observed[5]["stream"] is True
    assert observed[6]["seed"] == 42
    assert observed[7]["logprobs"] is True


def test_gemini_detector_uses_native_probe_and_usage_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://models.example.test/v1beta/models/gemini-test:generateContent"
        assert request.headers["x-goog-api-key"] == "secret"
        body = json.loads(request.content)
        assert body["contents"] == [{"role": "user", "parts": [{"text": "Reply with OK."}]}]
        assert body["generationConfig"] == {"temperature": 0, "maxOutputTokens": 8}
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "OK"}]}}],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
            },
        )

    endpoint = ModelEndpoint(
        display_name="Gemini",
        base_url="https://models.example.test/v1beta",
        model_name="gemini-test",
        protocol_profile="gemini_generate_content",
        encrypted_api_key="unused",
        api_key_mask="****test",
    )
    results = ProviderCapabilityDetector(transport=httpx.MockTransport(handler)).detect(
        endpoint, "secret", ["text_input", "usage_reporting", "audio_input"]
    )
    by_key = {result.capability_key: result for result in results}
    assert by_key["text_input"].status == CapabilityDetection.PASSED
    assert by_key["usage_reporting"].status == CapabilityDetection.PASSED
    assert by_key["audio_input"].status == CapabilityDetection.UNSUPPORTED_BY_ADAPTER
