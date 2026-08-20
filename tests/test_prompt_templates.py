import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.mongo import MongoDocumentStore
from app.main import create_app
from app.infrastructure.providers.contracts import ConnectionTestResult
from app.modules.benchmarks.prompts import PromptTemplateError, render_template
from tests.test_mongo_document_store import FakeClient


class SuccessfulTester:
    def test(self, _endpoint, _api_key: str) -> ConnectionTestResult:
        return ConnectionTestResult(True, "ok", 200)


def test_prompt_packages_validate_variables_and_snapshot_nonstandard_flags(tmp_path) -> None:
    app = create_app(
        Settings.local_development(database_url=f"sqlite:///{tmp_path / 'platform.db'}", secret_encryption_key=Fernet.generate_key().decode()),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(app) as api:
        invalid = api.post("/api/v1/prompt-packages", json={"name": "bad", "version": "1", "user_template": "{{ unsupported }}"})
        assert invalid.status_code == 422
        unsafe_scoring = api.post(
            "/api/v1/prompt-packages",
            json={"name": "unsafe", "version": "1", "user_template": "{{ question }}", "scoring_rule": {"type": "regex_match", "pattern": "(a+)+$"}},
        )
        assert unsafe_scoring.status_code == 422

        prompt = api.post(
            "/api/v1/prompt-packages",
            json={
                "name": "contextual",
                "version": "1",
                "prompt_type": "benchmark_variant",
                "system_message": "Return concise text.",
                "few_shot_examples": [{"role": "user", "content": "Example"}],
                "user_template": "{{ context }}\n{{ question }}\n{{ language }}",
            },
        )
        assert prompt.status_code == 201
        endpoint = api.post("/api/v1/model-endpoints", json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model"}).json()
        assert api.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = api.post("/api/v1/evaluation-runs", json={"model_endpoint_id": endpoint["id"], "prompt_package_id": prompt.json()["id"], "sample_limit": 1})
        assert run.status_code == 201
        flags = run.json()["configuration_snapshot"]["prompt_standardization"]
        assert flags == {"is_standard": False, "flags": ["non_standard_prompt", "modified_system_message", "custom_few_shot"]}
        attempt = api.get(f"/api/v1/evaluation-runs/{run.json()['id']}/attempts").json()[0]
        assert "2 + 2" in attempt["input_snapshot"]["messages"][-1]["content"]


def test_render_template_accepts_extra_variables() -> None:
    rendered = render_template("Rate: {{star}}/5", {"star": "4"}, extra_variables=frozenset({"star"}))
    assert rendered == "Rate: 4/5"


def test_render_template_still_rejects_unknown_variables_without_extra_variables() -> None:
    with pytest.raises(PromptTemplateError, match="star"):
        render_template("Rate: {{star}}/5", {"star": "4"})


def prompt_payload(*, name: str = "contextual", version: str = "1") -> dict[str, object]:
    return {
        "name": name,
        "version": version,
        "prompt_type": "user_custom",
        "system_message": "Return concise text.",
        "user_template": "{{ context }}\n{{ question }}",
        "few_shot_examples": [{"role": "user", "content": "Example"}],
        "output_format": {"type": "json_object"},
        "response_parser": {"path": "answer"},
        "scoring_rule": {"type": "exact_match"},
        "change_log": "Initial package.",
    }


def test_prompt_package_update_validates_conflicts_and_deletes_unused_records(tmp_path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            secret_encryption_key=Fernet.generate_key().decode(),
        )
    )
    with TestClient(app) as api:
        prompt = api.post("/api/v1/prompt-packages", json=prompt_payload()).json()
        updated_payload = prompt_payload(version="2")
        updated_payload["system_message"] = "Return only JSON."
        updated = api.put(f"/api/v1/prompt-packages/{prompt['id']}", json=updated_payload)
        assert updated.status_code == 200
        assert updated.json()["version"] == "2"
        assert updated.json()["system_message"] == "Return only JSON."

        invalid = api.put(
            f"/api/v1/prompt-packages/{prompt['id']}",
            json={**updated_payload, "user_template": "{{ unsupported }}"},
        )
        assert invalid.status_code == 422

        duplicate = api.post("/api/v1/prompt-packages", json=prompt_payload(name="another", version="1")).json()
        conflict = api.put(
            f"/api/v1/prompt-packages/{prompt['id']}",
            json=prompt_payload(name=duplicate["name"], version=duplicate["version"]),
        )
        assert conflict.status_code == 409
        assert api.put("/api/v1/prompt-packages/missing", json=updated_payload).status_code == 404

        deleted = api.delete(f"/api/v1/prompt-packages/{prompt['id']}")
        assert deleted.status_code == 200
        assert deleted.json()["id"] == prompt["id"]
        assert all(item["id"] != prompt["id"] for item in api.get("/api/v1/prompt-packages").json())
        assert api.delete("/api/v1/prompt-packages/missing").status_code == 404


def test_prompt_package_delete_rejects_run_and_suite_references(tmp_path) -> None:
    app = create_app(
        Settings.local_development(
            database_url=f"sqlite:///{tmp_path / 'platform.db'}",
            secret_encryption_key=Fernet.generate_key().decode(),
        ),
        connection_tester=SuccessfulTester(),
    )
    with TestClient(app) as api:
        run_prompt = api.post("/api/v1/prompt-packages", json=prompt_payload(name="run-reference")).json()
        endpoint = api.post(
            "/api/v1/model-endpoints",
            json={"base_url": "https://models.example.test/v1", "api_key": "secret", "model_name": "model"},
        ).json()
        assert api.post(f"/api/v1/model-endpoints/{endpoint['id']}/connection-test").status_code == 200
        run = api.post(
            "/api/v1/evaluation-runs",
            json={"model_endpoint_id": endpoint["id"], "prompt_package_id": run_prompt["id"], "sample_limit": 1},
        )
        assert run.status_code == 201
        edited_run_prompt = api.put(
            f"/api/v1/prompt-packages/{run_prompt['id']}",
            json={**prompt_payload(name="run-reference"), "system_message": "Changed after queueing."},
        )
        assert edited_run_prompt.status_code == 200
        stored_run = api.get(f"/api/v1/evaluation-runs/{run.json()['id']}").json()
        assert stored_run["configuration_snapshot"]["prompt_package"]["system_message"] == "Return concise text."
        assert api.delete(f"/api/v1/prompt-packages/{run_prompt['id']}").status_code == 409

        default_prompt = api.post("/api/v1/prompt-packages", json=prompt_payload(name="suite-default")).json()
        selection_prompt = api.post("/api/v1/prompt-packages", json=prompt_payload(name="suite-selection")).json()
        suite = {
            "name": "prompt-protection",
            "version": "1",
            "benchmark_list": [
                {"benchmark_id": "text-quick-check", "version": "1.0.0", "prompt_package_id": selection_prompt["id"]},
            ],
            "default_prompt_overrides": {"text-quick-check@1.0.0": default_prompt["id"]},
        }
        assert api.post("/api/v1/evaluation-suites", json=suite).status_code == 201
        assert api.delete(f"/api/v1/prompt-packages/{default_prompt['id']}").status_code == 409
        assert api.delete(f"/api/v1/prompt-packages/{selection_prompt['id']}").status_code == 409


def test_mongodb_prompt_package_update_and_delete_protection(tmp_path) -> None:
    client = FakeClient()
    settings = Settings.local_development(
        database_url="mongodb://mongo.test/platform",
        data_root=str(tmp_path),
        secret_encryption_key=Fernet.generate_key().decode(),
    )
    store = MongoDocumentStore(settings, client=client)
    app = create_app(settings, document_store=store)
    with TestClient(app) as api:
        prompt = api.post("/api/v1/prompt-packages", json=prompt_payload()).json()
        updated = api.put(
            f"/api/v1/prompt-packages/{prompt['id']}",
            json=prompt_payload(version="2"),
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == "2"

        duplicate = api.post("/api/v1/prompt-packages", json=prompt_payload(name="another", version="1")).json()
        conflict = api.put(
            f"/api/v1/prompt-packages/{prompt['id']}",
            json=prompt_payload(name=duplicate["name"], version=duplicate["version"]),
        )
        assert conflict.status_code == 409
        assert api.put("/api/v1/prompt-packages/missing", json=prompt_payload()).status_code == 404

        assert api.delete(f"/api/v1/prompt-packages/{prompt['id']}").status_code == 200
        assert api.delete("/api/v1/prompt-packages/missing").status_code == 404

        run_prompt = api.post("/api/v1/prompt-packages", json=prompt_payload(name="run-reference")).json()
        store.insert_document("evaluation_runs", {"prompt_package_id": run_prompt["id"]})
        assert api.delete(f"/api/v1/prompt-packages/{run_prompt['id']}").status_code == 409

        default_prompt = api.post("/api/v1/prompt-packages", json=prompt_payload(name="suite-default")).json()
        selection_prompt = api.post("/api/v1/prompt-packages", json=prompt_payload(name="suite-selection")).json()
        store.insert_document(
            "evaluation_suites",
            {
                "default_prompt_overrides": {"text-quick-check@1.0.0": default_prompt["id"]},
                "benchmark_list": [{"prompt_package_id": selection_prompt["id"]}],
            },
        )
        assert api.delete(f"/api/v1/prompt-packages/{default_prompt['id']}").status_code == 409
        assert api.delete(f"/api/v1/prompt-packages/{selection_prompt['id']}").status_code == 409
