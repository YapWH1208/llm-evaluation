from __future__ import annotations

from typing import Any


MEDIA_KINDS = frozenset({"image", "audio", "video", "file"})


class ContentValidationError(ValueError):
    pass


def normalize_content_parts(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate the database-neutral internal content representation for one message."""

    normalized: list[dict[str, Any]] = []
    for part in parts:
        part_type = part.get("type")
        if part_type == "text":
            text = part.get("text")
            if not isinstance(text, str) or not text:
                raise ContentValidationError("Text content parts require a non-empty text value.")
            normalized.append({"type": "text", "text": text})
            continue
        if part_type not in MEDIA_KINDS:
            raise ContentValidationError("Content part type must be text, image, audio, video, or file.")
        source = part.get("source")
        if not isinstance(source, dict):
            raise ContentValidationError("Media content parts require a source object.")
        source_keys = [key for key in ("asset_id", "url", "base64_data") if source.get(key)]
        if len(source_keys) != 1:
            raise ContentValidationError("Media content sources must contain exactly one of asset_id, url, or base64_data.")
        mime_type = part.get("mime_type")
        if not isinstance(mime_type, str) or "/" not in mime_type:
            raise ContentValidationError("Media content parts require a MIME type.")
        normalized.append({"type": part_type, "source": dict(source), "mime_type": mime_type.lower()})
    return normalized


def asset_content_part(asset_id: str, media_kind: str, mime_type: str) -> dict[str, object]:
    if media_kind not in MEDIA_KINDS:
        raise ContentValidationError("Unsupported stored media kind.")
    return {
        "type": media_kind,
        "source": {"asset_id": asset_id},
        "mime_type": mime_type,
    }
