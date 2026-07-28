import base64
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_media_asset_store_validates_content_and_returns_a_normalized_content_part(tmp_path: Path) -> None:
    png = b"\x89PNG\r\n\x1a\nminimal-png-content"
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", data_root=str(tmp_path / "data")))
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/assets",
            json={
                "filename": "../sample.png",
                "mime_type": "image/png",
                "base64_data": base64.b64encode(png).decode(),
            },
        )
        assert created.status_code == 201
        asset = created.json()
        assert asset["original_filename"] == "sample.png"
        assert asset["media_kind"] == "image"
        content_part = client.get(f"/api/v1/assets/{asset['id']}/content-part")
        assert content_part.json() == {"type": "image", "source": {"asset_id": asset["id"]}, "mime_type": "image/png"}
        downloaded = client.get(f"/api/v1/assets/{asset['id']}/download")
        assert downloaded.content == png
        assert downloaded.headers["x-content-type-options"] == "nosniff"
        assert downloaded.headers["cache-control"] == "private, no-store"
        assert downloaded.headers["content-security-policy"] == "sandbox; default-src 'none'"


def test_media_asset_store_rejects_declared_mime_mismatches(tmp_path: Path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'platform.db'}", data_root=str(tmp_path / "data")))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/assets",
            json={"filename": "not-an-image.png", "mime_type": "image/png", "base64_data": base64.b64encode(b"not a png").decode()},
        )
    assert response.status_code == 422
    assert "does not match" in response.json()["detail"]
