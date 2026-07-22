from __future__ import annotations

import base64
import binascii
import hashlib
from pathlib import Path
from uuid import uuid4


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
