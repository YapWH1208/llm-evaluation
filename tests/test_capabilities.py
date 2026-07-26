from pathlib import Path
import json

import httpx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app
from app.db.models import CapabilityDetection
from app.services.capability_detector import CapabilityDetectionResult
from app.services.capability_detector import OpenAIChatCompletionsCapabilityDetector
from app.db.models import ModelEndpoint

def test_capabilities_keep_user_declaration_separate(tmp_path: Path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", secret_encryption_key=Fernet.generate_key().decode()))
    with TestClient(app) as client:
        endpoint = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"secret","model_name":"m"}).json()
        response = client.put(f"/api/v1/model-endpoints/{endpoint['id']}/capabilities", json={"capability_key":"text_input","user_declared_status":"supported"})
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
                CapabilityDetectionResult("text_input", CapabilityDetection.PASSED, {"adapter_version": "test/1", "outcome": "passed"}),
                CapabilityDetectionResult("image_input", CapabilityDetection.UNSUPPORTED_BY_ADAPTER, {"adapter_version": "test/1", "outcome": "not_run"}),
            ]

    app = create_app(
        Settings(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", secret_encryption_key=Fernet.generate_key().decode()),
        capability_detector=Detector(),
    )
    with TestClient(app) as client:
        endpoint = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"secret","model_name":"m"}).json()
        client.put(f"/api/v1/model-endpoints/{endpoint['id']}/capabilities", json={"capability_key":"text_input","user_declared_status":"supported"})
        response = client.post(f"/api/v1/model-endpoints/{endpoint['id']}/capabilities/detect", json={"capability_keys":["text_input", "image_input"]})
        assert response.status_code == 200
        detected = {item["capability_key"]: item for item in response.json()}
        assert detected["text_input"]["user_declared_status"] == "supported"
        assert detected["text_input"]["auto_detection_status"] == "passed"
        assert detected["text_input"]["effective_status"] == "verified_by_both"
        assert detected["text_input"]["detection_evidence"] == {"adapter_version": "test/1", "outcome": "passed"}
        assert detected["image_input"]["auto_detection_status"] == "unsupported_by_adapter"


def test_openai_detector_probes_image_and_audio_and_marks_video_adapter_unsupported() -> None:
    observed: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}})

    endpoint = ModelEndpoint(display_name="test", base_url="https://models.example.test/v1", model_name="m", encrypted_api_key="unused", api_key_mask="****test")
    results = OpenAIChatCompletionsCapabilityDetector(httpx.MockTransport(handler)).detect(endpoint, "secret", ["image_input", "audio_input", "video_input"])
    by_key = {result.capability_key: result for result in results}
    assert by_key["image_input"].status == CapabilityDetection.PASSED
    assert by_key["audio_input"].status == CapabilityDetection.PASSED
    assert by_key["video_input"].status == CapabilityDetection.UNSUPPORTED_BY_ADAPTER
    assert observed[0]["messages"][0]["content"][1]["type"] == "image_url"
    assert observed[1]["messages"][0]["content"][1]["type"] == "input_audio"


def test_gemini_detector_uses_native_probe_and_usage_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://models.example.test/v1beta/models/gemini-test:generateContent"
        assert request.headers["x-goog-api-key"] == "secret"
        body = json.loads(request.content)
        assert body["contents"] == [{"role": "user", "parts": [{"text": "Reply with OK."}]}]
        assert body["generationConfig"] == {"temperature": 0, "maxOutputTokens": 8}
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "OK"}]}}], "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1}})

    endpoint = ModelEndpoint(display_name="Gemini", base_url="https://models.example.test/v1beta", model_name="gemini-test", protocol_profile="gemini_generate_content", encrypted_api_key="unused", api_key_mask="****test")
    results = OpenAIChatCompletionsCapabilityDetector(httpx.MockTransport(handler)).detect(endpoint, "secret", ["text_input", "usage_reporting", "audio_input"])
    by_key = {result.capability_key: result for result in results}
    assert by_key["text_input"].status == CapabilityDetection.PASSED
    assert by_key["usage_reporting"].status == CapabilityDetection.PASSED
    assert by_key["audio_input"].status == CapabilityDetection.UNSUPPORTED_BY_ADAPTER
