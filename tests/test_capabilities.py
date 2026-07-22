from pathlib import Path
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app

def test_capabilities_keep_user_declaration_separate(tmp_path: Path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", secret_encryption_key=Fernet.generate_key().decode()))
    with TestClient(app) as client:
        endpoint = client.post("/api/v1/model-endpoints", json={"base_url":"https://models.example.test/v1","api_key":"secret","model_name":"m"}).json()
        response = client.put(f"/api/v1/model-endpoints/{endpoint['id']}/capabilities", json={"capability_key":"text_input","user_declared_status":"supported"})
        assert response.status_code == 200
        assert response.json()["effective_status"] == "user_verified"
        listed = client.get(f"/api/v1/model-endpoints/{endpoint['id']}/capabilities")
        assert listed.json()[0]["auto_detection_status"] == "not_tested"
