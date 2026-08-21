from __future__ import annotations

import re
from collections.abc import Iterable


EVALUATION_TYPES = frozenset({"classification", "generation", "code", "language_modeling", "custom"})
MAX_DATASET_METADATA_VALUES = 32
MAX_DATASET_METADATA_VALUE_LENGTH = 64
_CAPABILITY = re.compile(r"^[a-z0-9][a-z0-9_]*$")
_LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")


class DatasetMetadataError(ValueError):
    """Raised when reusable dataset metadata cannot be normalized safely."""


def normalize_capabilities(values: Iterable[str]) -> list[str]:
    normalized: set[str] = set()
    for value in values:
        item = _bounded_text(value, "capability").lower()
        item = re.sub(r"[\s-]+", "_", item)
        if not _CAPABILITY.fullmatch(item):
            raise DatasetMetadataError("Capabilities may contain lowercase letters, numbers, and underscores.")
        normalized.add(item)
    return _bounded_collection(normalized, "capabilities")


def normalize_languages(values: Iterable[str]) -> list[str]:
    normalized: set[str] = set()
    for value in values:
        item = _bounded_text(value, "language tag")
        if not _LANGUAGE_TAG.fullmatch(item):
            raise DatasetMetadataError("Languages must use BCP 47-compatible tags such as en or zh-Hans-CN.")
        parts = item.split("-")
        canonical = [parts[0].lower()]
        for part in parts[1:]:
            if len(part) == 4 and part.isalpha():
                canonical.append(part.title())
            elif (len(part) == 2 and part.isalpha()) or (len(part) == 3 and part.isdigit()):
                canonical.append(part.upper())
            else:
                canonical.append(part.lower())
        normalized.add("-".join(canonical))
    return _bounded_collection(normalized, "languages")


def normalize_evaluation_type(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    if normalized not in EVALUATION_TYPES:
        raise DatasetMetadataError(
            "Evaluation type must be classification, generation, code, language_modeling, or custom."
        )
    return normalized


def _bounded_text(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise DatasetMetadataError(f"Each {label} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise DatasetMetadataError(f"Each {label} must not be blank.")
    if len(normalized) > MAX_DATASET_METADATA_VALUE_LENGTH:
        raise DatasetMetadataError(f"Each {label} must be at most {MAX_DATASET_METADATA_VALUE_LENGTH} characters.")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise DatasetMetadataError(f"Each {label} must not contain control characters.")
    return normalized


def _bounded_collection(values: set[str], label: str) -> list[str]:
    if len(values) > MAX_DATASET_METADATA_VALUES:
        raise DatasetMetadataError(f"Datasets may declare at most {MAX_DATASET_METADATA_VALUES} {label}.")
    return sorted(values, key=lambda item: (item.lower(), item))
