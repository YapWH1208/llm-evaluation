from __future__ import annotations

import base64
import binascii
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.content import asset_content_part
from app.core.errors import NotFoundError, ValidationError
from app.modules.reports.ports import AssetRepository

SUPPORTED_MIME_TYPES = {
    "image/png": "image",
    "image/jpeg": "image",
    "image/gif": "image",
    "image/webp": "image",
    "audio/wav": "audio",
    "audio/mpeg": "audio",
    "video/mp4": "video",
    "video/webm": "video",
    "application/pdf": "file",
}
MAX_ASSET_BYTES = 25 * 1024 * 1024


class MediaAssetError(ValueError):
    pass


class AssetService:
    """Media-asset validation, storage, and lookup independent of database kind."""

    def __init__(self, repository: AssetRepository, data_root: str) -> None:
        self._repository = repository
        self._data_root = data_root

    def create(self, payload: Any) -> Any:
        try:
            data, mime_type, media_kind = decode_and_validate_asset(payload.base64_data, payload.mime_type)
            sha256, storage_path = store_asset(self._data_root, data)
        except MediaAssetError as error:
            raise ValidationError(str(error)) from error
        existing = self._repository.find_by_digest(sha256)
        if existing is not None:
            return existing
        return self._repository.create_asset(
            {
                "original_filename": safe_filename(payload.filename),
                "media_kind": media_kind,
                "mime_type": mime_type,
                "size_bytes": len(data),
                "sha256": sha256,
                "storage_path": storage_path,
                "created_at": datetime.now(timezone.utc),
            }
        )

    def get(self, asset_id: str) -> Any:
        asset = self._repository.get_asset(asset_id)
        if asset is None:
            raise NotFoundError("Media asset not found", context={"asset_id": asset_id})
        return asset

    def content_part(self, asset_id: str) -> dict[str, object]:
        asset = self.get(asset_id)
        return asset_content_part(
            str(_value(asset, "id")), str(_value(asset, "media_kind")), str(_value(asset, "mime_type"))
        )

    def download(self, asset_id: str) -> tuple[Path, str, str]:
        asset = self.get(asset_id)
        try:
            path = safe_asset_path(self._data_root, str(_value(asset, "storage_path")))
        except MediaAssetError as error:
            raise NotFoundError(str(error), context={"asset_id": asset_id}) from error
        return path, str(_value(asset, "mime_type")), str(_value(asset, "original_filename"))


def decode_and_validate_asset(base64_data: str, mime_type: str) -> tuple[bytes, str, str]:
    normalized_mime_type = mime_type.lower().strip()
    media_kind = SUPPORTED_MIME_TYPES.get(normalized_mime_type)
    if media_kind is None:
        raise MediaAssetError("Unsupported media MIME type.")
    try:
        data = base64.b64decode(base64_data, validate=True)
    except (binascii.Error, ValueError) as error:
        raise MediaAssetError("Asset data must be valid base64.") from error
    if not data:
        raise MediaAssetError("Asset data must not be empty.")
    if len(data) > MAX_ASSET_BYTES:
        raise MediaAssetError("Asset exceeds the 25 MiB upload limit.")
    if not _has_expected_signature(data, normalized_mime_type):
        raise MediaAssetError("Asset content does not match its declared MIME type.")
    return data, normalized_mime_type, media_kind


def store_asset(data_root: str, data: bytes) -> tuple[str, str]:
    digest = hashlib.sha256(data).hexdigest()
    root = Path(data_root).resolve() / "assets"
    destination = root / digest[:2] / digest
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temporary = destination.with_name(f"{digest}.{uuid4().hex}.part")
        temporary.write_bytes(data)
        temporary.replace(destination)
    return digest, str(destination.resolve())


def safe_asset_path(data_root: str, storage_path: str) -> Path:
    root = (Path(data_root).resolve() / "assets").resolve()
    candidate = Path(storage_path).resolve()
    if not candidate.is_relative_to(root):
        raise MediaAssetError("Stored asset path is outside the asset store.")
    if not candidate.is_file():
        raise MediaAssetError("Stored asset file is unavailable.")
    return candidate


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    return name[:255] or "asset.bin"


def _value(asset: Any, key: str) -> Any:
    return asset.get(key) if isinstance(asset, dict) else getattr(asset, key)


def _has_expected_signature(data: bytes, mime_type: str) -> bool:
    signatures = {
        "image/png": lambda value: value.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": lambda value: value.startswith(b"\xff\xd8\xff"),
        "image/gif": lambda value: value.startswith((b"GIF87a", b"GIF89a")),
        "image/webp": lambda value: value.startswith(b"RIFF") and value[8:12] == b"WEBP",
        "audio/wav": lambda value: value.startswith(b"RIFF") and value[8:12] == b"WAVE",
        "audio/mpeg": lambda value: value.startswith(b"ID3") or value.startswith(b"\xff\xfb"),
        "video/mp4": lambda value: len(value) >= 12 and value[4:8] == b"ftyp",
        "video/webm": lambda value: value.startswith(b"\x1a\x45\xdf\xa3"),
        "application/pdf": lambda value: value.startswith(b"%PDF-"),
    }
    return signatures[mime_type](data)
