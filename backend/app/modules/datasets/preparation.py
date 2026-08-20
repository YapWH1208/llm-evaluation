from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import zipfile
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse
from uuid import uuid4

import httpx
from app.core.config import DEFAULT_DATASET_DOWNLOAD_MAX_BYTES, Settings
from app.db.models import DatasetStatus
from app.modules.datasets.records import iter_dataset_records, iter_delimited_rows
from app.modules.datasets.records import DatasetRecordError
from app.infrastructure.network.outbound import OutboundNetworkError, pinned_outbound_transport, validate_outbound_url


class DatasetError(ValueError):
    pass


class DatasetDownloadPaused(DatasetError):
    pass


MAX_PREPARED_ARCHIVE_FILES = 10_000
MAX_PREPARED_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_DOWNLOAD_REDIRECTS = 5
MATERIAL_DATASET_SOURCE_FIELDS = (
    "source_url",
    "revision",
    "checksum",
    "license_text",
    "credential_binding_id",
)
INACTIVE_DATASET_EDIT_RESET_STATUSES = frozenset(
    {
        DatasetStatus.NOT_DOWNLOADED.value,
        DatasetStatus.UPDATE_AVAILABLE.value,
        DatasetStatus.LICENSE_REQUIRED.value,
        DatasetStatus.CREDENTIAL_REQUIRED.value,
        DatasetStatus.CORRUPTED.value,
        DatasetStatus.FAILED.value,
    }
)


def resolve_dataset_source(
    source_url: str,
    revision: str,
    credential_binding_id: str | None,
    settings: Settings | None = None,
) -> tuple[str, dict[str, str]]:
    """Resolve one HTTPS or Hugging Face source under the deployment policy."""

    parsed = urlparse(source_url)
    if parsed.scheme == "hf":
        path_parts = [part for part in parsed.path.split("/") if part]
        if parsed.netloc == "datasets" and len(path_parts) >= 3:
            repository = "/".join(path_parts[:2])
            relative_path = "/".join(path_parts[2:])
        else:
            if not parsed.netloc or len(path_parts) < 2:
                raise DatasetError(
                    "Hugging Face sources must use hf://owner/repository/path/to/file "
                    "or hf://datasets/owner/repository/path/to/file."
                )
            repository = f"{parsed.netloc}/{path_parts[0]}"
            relative_path = "/".join(path_parts[1:])
        resolved = f"https://huggingface.co/datasets/{repository}/resolve/{quote(revision, safe='')}/{quote(relative_path, safe='/')}"
    elif parsed.scheme == "https" and parsed.netloc:
        resolved = source_url
    else:
        raise DatasetError(
            "Dataset source must be an HTTPS URL, hf://owner/repository/path, "
            "or hf://datasets/owner/repository/path. "
            "Use the upload endpoint for local files."
        )

    _validate_remote_dataset_url(
        resolved,
        allowed_hosts=settings.dataset_allowed_hosts if settings is not None else (),
    )
    return resolved, _credential_headers(resolved, credential_binding_id, settings)


def _credential_headers(
    source_url: str,
    credential_binding_id: str | None,
    settings: Settings | None,
) -> dict[str, str]:
    if credential_binding_id is None:
        return {}
    binding = settings.dataset_credential_bindings.get(credential_binding_id) if settings is not None else None
    if binding is None:
        raise DatasetError(
            f"Dataset credential binding {credential_binding_id!r} is not configured. "
            "Ask an administrator to configure LLE_DATASET_CREDENTIAL_BINDINGS_JSON."
        )
    host = urlparse(source_url).hostname
    if host is None or host.lower().rstrip(".") not in binding.allowed_hosts:
        raise DatasetError(
            f"Dataset credential binding {credential_binding_id!r} is not authorized for this source host."
        )
    token = os.getenv(binding.environment_variable)
    if not token:
        raise DatasetError(f"Dataset credential binding {credential_binding_id!r} is not available in this deployment.")
    return {"Authorization": f"Bearer {token}"}


def _validate_remote_dataset_url(source_url: str, *, allowed_hosts: tuple[str, ...]) -> tuple[str, ...]:
    parsed = urlparse(source_url)
    if parsed.scheme != "https":
        raise DatasetError("Dataset URLs must use HTTPS.")
    host = parsed.hostname
    if not host:
        raise DatasetError("Dataset URL must include a hostname.")
    normalized_host = host.lower().rstrip(".")
    if allowed_hosts and not any(
        normalized_host == item or normalized_host.endswith(f".{item}") for item in allowed_hosts
    ):
        raise DatasetError("Dataset URL host is not allowed by the configured network policy.")
    try:
        return validate_outbound_url(source_url)
    except OutboundNetworkError as error:
        raise DatasetError(str(error)) from error


def _host_not_allowed(host: str | None, allowed_hosts: tuple[str, ...]) -> bool:
    """Apply the deployment host policy to one redirect hop (empty = allow all)."""

    if not allowed_hosts or host is None:
        return False
    normalized = host.lower().rstrip(".")
    return not any(normalized == item or normalized.endswith(f".{item}") for item in allowed_hosts)


def dataset_source_suffix(source_url: str) -> str:
    suffix = Path(urlparse(source_url).path).suffix.lower()
    return suffix if suffix in {".json", ".jsonl", ".csv", ".tsv", ".txt", ".zip", ".parquet"} else ".bin"


def write_dataset_source(
    source: str,
    target: Path,
    headers: dict[str, str],
    on_chunk: Callable[[], None] | None = None,
    *,
    max_bytes: int = DEFAULT_DATASET_DOWNLOAD_MAX_BYTES,
    allowed_hosts: tuple[str, ...] = (),
) -> str:
    """Redirects are followed only after every hop passes the same outbound URL and host-policy validation as the original source, so no unvalidated destination is ever contacted and the redirect body is never written to disk."""

    digest = hashlib.sha256()
    current = source
    source_host = urlparse(source).hostname
    hop_headers = headers
    for _hop in range(MAX_DOWNLOAD_REDIRECTS + 1):
        try:
            addresses = validate_outbound_url(current)
        except OutboundNetworkError as error:
            raise DatasetError(str(error)) from error
        with httpx.Client(transport=pinned_outbound_transport(addresses), timeout=60, follow_redirects=False) as client:
            with client.stream("GET", current, headers=hop_headers) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise DatasetError("Dataset source redirected without a Location header.")
                    current = urljoin(current, location)
                    if urlparse(current).scheme != "https":
                        raise DatasetError("Dataset redirects must use HTTPS.")
                    if _host_not_allowed(urlparse(current).hostname, allowed_hosts):
                        raise DatasetError("Dataset redirect target is not allowed by the configured network policy.")
                    if urlparse(current).hostname != source_host:
                        hop_headers = {key: value for key, value in headers.items() if key.lower() != "authorization"}
                    continue
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                    raise DatasetError(f"Dataset download exceeds the configured {max_bytes} byte limit.")
                written = 0
                with target.open("wb") as output_file:
                    for chunk in response.iter_bytes():
                        written += len(chunk)
                        if written > max_bytes:
                            raise DatasetError(f"Dataset download exceeds the configured {max_bytes} byte limit.")
                        output_file.write(chunk)
                        digest.update(chunk)
                        if on_chunk:
                            on_chunk()
                return digest.hexdigest()
    raise DatasetError(f"Dataset source redirected more than {MAX_DOWNLOAD_REDIRECTS} times.")


def prepare_dataset_cache(target: Path) -> Path:
    """Build an atomic, database-neutral sample index for a verified cache file."""

    if not target.is_file():
        raise DatasetError("Dataset cache file is unavailable for preparation.")
    destination = target.parent / "prepared"
    temporary = target.parent / f".prepared-{uuid4().hex}"
    previous: Path | None = None
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        source_root = temporary / "source"
        source_root.mkdir()
        source_files = _materialize_dataset_sources(target, source_root)
        index_path = temporary / "sample-index.jsonl"
        record_count = 0
        with index_path.open("w", encoding="utf-8", newline="\n") as index_file:
            for source_file in source_files:
                relative = source_file.relative_to(source_root).as_posix()
                for record_number in _indexable_record_numbers(source_file):
                    index_file.write(
                        json.dumps({"source": relative, "record_number": record_number}, separators=(",", ":")) + "\n"
                    )
                    record_count += 1
        manifest_path = temporary / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "format": "lle.sample-index/v1",
                    "source_files": [path.relative_to(source_root).as_posix() for path in source_files],
                    "record_count": record_count,
                    "index_path": "sample-index.jsonl",
                },
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        previous = target.parent / f".prepared-previous-{uuid4().hex}"
        if destination.exists():
            destination.replace(previous)
        try:
            temporary.replace(destination)
        except Exception:
            if previous.exists() and not destination.exists():
                previous.replace(destination)
            raise
        if previous is not None and previous.exists():
            shutil.rmtree(previous)
        return destination / "manifest.json"
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        if previous is not None and previous.exists() and not destination.exists():
            previous.replace(destination)
        raise


def clear_prepared_dataset_cache(prepared_path: str | None, data_root: str) -> None:
    if not prepared_path:
        return
    root = (Path(data_root).resolve() / "datasets").resolve()
    manifest = Path(prepared_path).resolve()
    prepared = manifest.parent
    if prepared.name != "prepared" or not prepared.is_relative_to(root):
        raise DatasetError("Prepared dataset cache path is outside the configured dataset root.")
    if prepared.exists():
        shutil.rmtree(prepared)


def validate_prepared_dataset_cache(prepared_path: str | None, data_root: str) -> bool:
    if not prepared_path:
        return False
    root = (Path(data_root).resolve() / "datasets").resolve()
    manifest = Path(prepared_path).resolve()
    return (
        manifest.is_relative_to(root)
        and manifest.name == "manifest.json"
        and manifest.parent.name == "prepared"
        and manifest.is_file()
    )


def _materialize_dataset_sources(target: Path, source_root: Path) -> list[Path]:
    if zipfile.is_zipfile(target):
        source_files: list[Path] = []
        total_size = 0
        with zipfile.ZipFile(target) as archive:
            entries = [entry for entry in archive.infolist() if not entry.is_dir()]
            if len(entries) > MAX_PREPARED_ARCHIVE_FILES:
                raise DatasetError("Dataset archive contains too many files to prepare safely.")
            for entry in entries:
                total_size += entry.file_size
                if total_size > MAX_PREPARED_ARCHIVE_BYTES:
                    raise DatasetError("Dataset archive exceeds the safe preparation size limit.")
                output = (source_root / entry.filename).resolve()
                if not output.is_relative_to(source_root.resolve()):
                    raise DatasetError("Dataset archive contains an unsafe file path.")
                output.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, output.open("wb") as destination:
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
                source_files.append(output)
        return source_files
    output = source_root / f"dataset{target.suffix.lower() or '.bin'}"
    shutil.copyfile(target, output)
    return [output]


def _indexable_record_numbers(path: Path) -> Iterator[int]:
    if path.suffix.lower() == ".json":
        try:
            value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError) as error:
            raise DatasetError(f"Dataset JSON source could not be parsed: {error}") from error
        if isinstance(value, dict):
            yield 1
            return
        if isinstance(value, list):
            for number in range(1, len(value) + 1):
                yield number
            return
        raise DatasetError("Dataset JSON sources must be an object or an array of objects.")
    if path.suffix.lower() in {".csv", ".tsv"}:
        delimiter = "," if path.suffix.lower() == ".csv" else "\t"
        try:
            for start_line, _fields in iter_delimited_rows(path, delimiter=delimiter):
                yield start_line
        except (csv.Error, OSError) as error:
            raise DatasetError(f"Dataset delimited source could not be parsed: {error}") from error
        return
    if path.suffix.lower() not in {".json", ".jsonl", ".csv", ".tsv", ".txt"}:
        yield 1
        return
    try:
        with path.open("r", encoding="utf-8", errors="replace") as source:
            found = False
            for number, line in enumerate(source, start=1):
                if line.strip():
                    found = True
                    yield number
    except OSError as error:
        raise DatasetError("Dataset source could not be read during preparation.") from error
    if not found:
        yield 1


def dataset_disk_usage(data_root: str) -> dict[str, int | str]:
    root = (Path(data_root).resolve() / "datasets").resolve()
    root.mkdir(parents=True, exist_ok=True)
    used = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
    disk = shutil.disk_usage(root)
    return {"root": str(root), "cache_bytes": used, "available_bytes": disk.free, "total_bytes": disk.total}


def preview_dataset_records(prepared_path: str, data_root: str, *, limit: int) -> dict[str, object]:
    fields: list[str] = []
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for record in iter_dataset_records(prepared_path, data_root, limit=limit):
        raw_fields = record["fields"]
        if not isinstance(raw_fields, dict):
            continue
        for key in raw_fields:
            if key not in seen:
                seen.add(key)
                fields.append(key)
        rows.append({str(key): _stringify_preview_value(value) for key, value in raw_fields.items()})
    return {"fields": fields, "rows": rows}


def validate_dataset_field_defaults(
    prepared_path: str | None,
    data_root: str,
    *,
    input_field: str | None,
    reference_field: str | None,
) -> None:
    if input_field is not None and input_field == reference_field:
        raise DatasetError("Input and reference fields must name different dataset columns.")
    if prepared_path is None:
        return
    try:
        preview = preview_dataset_records(prepared_path, data_root, limit=50)
    except DatasetRecordError as error:
        raise DatasetError(f"Dataset preview schema is unavailable: {error}") from error
    fields = {str(field) for field in preview["fields"]}
    missing = [field for field in (input_field, reference_field) if field is not None and field not in fields]
    if missing:
        raise DatasetError(
            "Dataset field selection is not present in the current preview schema: " + ", ".join(missing) + "."
        )


def dataset_edit_lifecycle_updates(
    current: Mapping[str, object], values: Mapping[str, object]
) -> dict[str, object | None]:
    changed_fields = {field for field in MATERIAL_DATASET_SOURCE_FIELDS if current.get(field) != values.get(field)}
    if (
        not changed_fields
        or current.get("local_path")
        or current.get("prepared_path")
        or current.get("status") not in INACTIVE_DATASET_EDIT_RESET_STATUSES
    ):
        return {}
    lifecycle: dict[str, object | None] = {"error_message": None}
    license_accepted_at = current.get("license_accepted_at")
    if "license_text" in changed_fields:
        license_accepted_at = None
        lifecycle["license_accepted_at"] = None
    lifecycle["status"] = (
        DatasetStatus.LICENSE_REQUIRED.value
        if values.get("license_text") and license_accepted_at is None
        else DatasetStatus.NOT_DOWNLOADED.value
    )
    return lifecycle


def _stringify_preview_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
