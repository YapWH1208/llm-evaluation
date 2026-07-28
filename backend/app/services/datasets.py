from __future__ import annotations

import hashlib
import ipaddress
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from socket import getaddrinfo
from urllib.parse import quote, unquote, urlparse
from urllib.request import url2pathname

import httpx
from sqlalchemy.orm import Session

from app.db.models import DatasetStatus, DatasetVersion


class DatasetError(ValueError):
    pass


class DatasetDownloadPaused(DatasetError):
    pass


DatasetDownloader = Callable[[str, str, dict[str, str]], tuple[Path | str, dict[str, str]]]
DATASET_DOWNLOADER_PLUGINS: dict[str, DatasetDownloader] = {}


def register_dataset_downloader(scheme: str, downloader: DatasetDownloader) -> None:
    """Register a source resolver without coupling dataset storage to a provider."""

    normalized = scheme.lower().strip().removesuffix(":")
    if not normalized or normalized in {"http", "https", "file", "hf"}:
        raise DatasetError("Custom downloader schemes must be non-empty and cannot replace built-in sources.")
    DATASET_DOWNLOADER_PLUGINS[normalized] = downloader


def resolve_dataset_source(
    source_url: str,
    revision: str,
    credential_env_var: str | None,
) -> tuple[Path | str, dict[str, str]]:
    """Resolve HTTP(S), Hugging Face, and explicitly provided local dataset sources."""

    headers: dict[str, str] = {}
    if credential_env_var:
        token = os.getenv(credential_env_var)
        if not token:
            raise DatasetError(f"Dataset credential environment variable {credential_env_var} is not configured.")
        headers["Authorization"] = f"Bearer {token}"
    parsed = urlparse(source_url)
    if parsed.scheme == "hf":
        repository = parsed.netloc
        path_parts = [part for part in parsed.path.split("/") if part]
        if not repository or len(path_parts) < 2:
            raise DatasetError("Hugging Face sources must use hf://owner/repository/path/to/file.")
        repository = f"{repository}/{path_parts[0]}"
        relative_path = "/".join(path_parts[1:])
        resolved = f"https://huggingface.co/{repository}/resolve/{quote(revision, safe='')}/{quote(relative_path, safe='/')}"
        _validate_remote_dataset_url(resolved)
        return resolved, headers
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        _validate_remote_dataset_url(source_url)
        return source_url, headers
    if parsed.scheme == "file":
        return Path(url2pathname(unquote(parsed.path))).resolve(), headers
    if not parsed.scheme:
        return Path(source_url).expanduser().resolve(), headers
    plugin = DATASET_DOWNLOADER_PLUGINS.get(parsed.scheme.lower())
    if plugin is not None:
        return plugin(source_url, revision, headers)
    raise DatasetError("Dataset source must be HTTP(S), hf://owner/repository/path, file://, a local file path, or a registered downloader plugin.")


def _validate_remote_dataset_url(source_url: str) -> None:
    parsed = urlparse(source_url)
    host = parsed.hostname
    if not host:
        raise DatasetError("Dataset URL must include a hostname.")
    allowed_hosts = {item.strip().lower() for item in os.getenv("LLE_DATASET_ALLOWED_HOSTS", "").split(",") if item.strip()}
    if allowed_hosts and not any(host.lower() == item or host.lower().endswith(f".{item}") for item in allowed_hosts):
        raise DatasetError("Dataset URL host is not allowed by the configured network policy.")
    try:
        addresses = {item[4][0] for item in getaddrinfo(host, None)}
    except OSError as error:
        raise DatasetError("Dataset URL hostname could not be resolved.") from error
    for address in addresses:
        parsed_address = ipaddress.ip_address(address)
        if parsed_address.is_private or parsed_address.is_loopback or parsed_address.is_link_local or parsed_address.is_multicast or parsed_address.is_reserved or parsed_address.is_unspecified:
            raise DatasetError("Dataset URL resolves to a private or restricted network address.")


def write_dataset_source(source: Path | str, target: Path, headers: dict[str, str], on_chunk: Callable[[], None] | None = None) -> str:
    """Stream a configured source to a temporary file and return its SHA-256 digest."""

    digest = hashlib.sha256()
    if isinstance(source, Path):
        if not source.is_file():
            raise DatasetError("Dataset local source file was not found.")
        with source.open("rb") as input_file, target.open("wb") as output_file:
            for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                output_file.write(chunk)
                digest.update(chunk)
                if on_chunk:
                    on_chunk()
        return digest.hexdigest()
    with httpx.stream("GET", source, headers=headers, timeout=60, follow_redirects=False) as response:
        response.raise_for_status()
        with target.open("wb") as output_file:
            for chunk in response.iter_bytes():
                output_file.write(chunk)
                digest.update(chunk)
                if on_chunk:
                    on_chunk()
    return digest.hexdigest()


def accept_license(session: Session, dataset: DatasetVersion) -> DatasetVersion:
    from datetime import datetime, timezone
    dataset.license_accepted_at = datetime.now(timezone.utc)
    if dataset.status == DatasetStatus.LICENSE_REQUIRED.value:
        dataset.status = DatasetStatus.NOT_DOWNLOADED.value
    session.commit(); session.refresh(dataset)
    return dataset


def download_dataset(session: Session, dataset: DatasetVersion, data_root: str) -> DatasetVersion:
    if not dataset.source_url:
        raise DatasetError("Dataset has no downloadable source URL.")
    if dataset.license_text and dataset.license_accepted_at is None:
        dataset.status = DatasetStatus.LICENSE_REQUIRED.value; session.commit()
        raise DatasetError("Dataset license must be accepted before download.")
    destination = Path(data_root).resolve() / "datasets" / dataset.dataset_id / dataset.version / dataset.revision
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / "dataset.bin"; temporary = destination / "dataset.part"
    dataset.status = DatasetStatus.DOWNLOADING.value; dataset.error_message = None; session.commit()
    try:
        source, headers = resolve_dataset_source(dataset.source_url, dataset.revision, dataset.credential_env_var)
        def ensure_not_paused() -> None:
            session.refresh(dataset)
            if dataset.status == DatasetStatus.WAITING.value:
                raise DatasetDownloadPaused("Dataset download was paused and can be retried.")

        actual_checksum = write_dataset_source(source, temporary, headers, ensure_not_paused)
        dataset.status = DatasetStatus.VERIFYING.value; session.commit()
        if dataset.checksum and dataset.checksum.lower() != actual_checksum:
            temporary.unlink(missing_ok=True)
            raise DatasetError("Dataset checksum verification failed.")
        temporary.replace(target)
        dataset.checksum = actual_checksum; dataset.local_path = str(target); dataset.size_bytes = target.stat().st_size; dataset.status = DatasetStatus.READY.value
    except DatasetDownloadPaused as error:
        dataset.status = DatasetStatus.WAITING.value
        dataset.error_message = None
        session.commit()
        raise DatasetError(str(error)) from error
    except (httpx.HTTPStatusError, DatasetError) as error:
        dataset.status = DatasetStatus.CREDENTIAL_REQUIRED.value if dataset.credential_env_var and ("environment variable" in str(error) or getattr(getattr(error, "response", None), "status_code", 0) in {401, 403}) else DatasetStatus.FAILED.value; dataset.error_message = str(error)[:500]
        session.commit()
        raise DatasetError(str(error)) from error
    except (httpx.HTTPError, OSError) as error:
        dataset.status = DatasetStatus.FAILED.value; dataset.error_message = str(error)[:500]
        session.commit()
        raise DatasetError(str(error)) from error
    session.commit(); session.refresh(dataset)
    return dataset


def pause_dataset_download(session: Session, dataset: DatasetVersion) -> DatasetVersion:
    if dataset.status not in {DatasetStatus.DOWNLOADING.value, DatasetStatus.VERIFYING.value, DatasetStatus.PREPARING.value}:
        raise DatasetError("Only an active dataset download can be paused.")
    dataset.status = DatasetStatus.WAITING.value
    dataset.error_message = None
    session.commit()
    session.refresh(dataset)
    return dataset


def validate_dataset_cache(session: Session, dataset: DatasetVersion, data_root: str) -> DatasetVersion:
    if not dataset.local_path:
        raise DatasetError("Dataset has no cached file to validate.")
    root = (Path(data_root).resolve() / "datasets").resolve()
    target = Path(dataset.local_path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        dataset.status = DatasetStatus.CORRUPTED.value
        dataset.error_message = "Dataset cache file is missing or outside the configured dataset root."
        session.commit()
        raise DatasetError(dataset.error_message)
    dataset.status = DatasetStatus.VERIFYING.value
    session.commit()
    digest = hashlib.sha256()
    with target.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    checksum = digest.hexdigest()
    if dataset.checksum and checksum != dataset.checksum.lower():
        dataset.status = DatasetStatus.CORRUPTED.value
        dataset.error_message = "Dataset cache checksum verification failed."
        session.commit()
        raise DatasetError(dataset.error_message)
    dataset.checksum = checksum
    dataset.size_bytes = target.stat().st_size
    dataset.status = DatasetStatus.READY.value
    dataset.error_message = None
    session.commit()
    session.refresh(dataset)
    return dataset


def dataset_disk_usage(data_root: str) -> dict[str, int | str]:
    root = (Path(data_root).resolve() / "datasets").resolve()
    root.mkdir(parents=True, exist_ok=True)
    used = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
    disk = shutil.disk_usage(root)
    return {"root": str(root), "cache_bytes": used, "available_bytes": disk.free, "total_bytes": disk.total}


def clear_dataset_cache(session: Session, dataset: DatasetVersion, data_root: str) -> DatasetVersion:
    if dataset.local_path:
        root = (Path(data_root).resolve() / "datasets").resolve()
        target = Path(dataset.local_path).resolve()
        if not target.is_relative_to(root):
            raise DatasetError("Dataset cache path is outside the configured dataset root.")
        target.unlink(missing_ok=True)
    dataset.local_path = None
    dataset.size_bytes = None
    dataset.status = DatasetStatus.LICENSE_REQUIRED.value if dataset.license_text and dataset.license_accepted_at is None else DatasetStatus.NOT_DOWNLOADED.value
    dataset.error_message = None
    session.commit(); session.refresh(dataset)
    return dataset


def store_uploaded_dataset(
    session: Session,
    dataset: DatasetVersion,
    *,
    filename: str,
    content: bytes,
    data_root: str,
) -> DatasetVersion:
    """Atomically persist a user-uploaded dataset outside the primary database."""

    if not content:
        raise DatasetError("Uploaded dataset is empty.")
    if len(content) > 64 * 1024 * 1024:
        raise DatasetError("Uploaded dataset exceeds the 64 MiB upload limit.")
    safe_name = Path(filename).name
    if not safe_name or safe_name in {".", ".."}:
        raise DatasetError("Uploaded dataset filename is invalid.")
    if Path(safe_name).suffix.lower() not in {".json", ".jsonl", ".csv", ".tsv", ".txt", ".zip", ".parquet"}:
        raise DatasetError("Uploaded dataset file type is not supported.")
    if dataset.license_text and dataset.license_accepted_at is None:
        dataset.status = DatasetStatus.LICENSE_REQUIRED.value
        session.commit()
        raise DatasetError("Dataset license must be accepted before upload.")
    destination = (Path(data_root).resolve() / "datasets" / "uploads" / dataset.id).resolve()
    root = (Path(data_root).resolve() / "datasets").resolve()
    if not destination.is_relative_to(root):
        raise DatasetError("Dataset upload path is outside the configured dataset root.")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / safe_name
    temporary = destination / f".{safe_name}.part"
    checksum = hashlib.sha256(content).hexdigest()
    if dataset.checksum and dataset.checksum.lower() != checksum:
        dataset.status = DatasetStatus.CORRUPTED.value
        dataset.error_message = "Uploaded dataset checksum verification failed."
        session.commit()
        raise DatasetError(dataset.error_message)
    temporary.write_bytes(content)
    temporary.replace(target)
    dataset.source_url = target.as_uri()
    dataset.checksum = checksum
    dataset.size_bytes = len(content)
    dataset.local_path = str(target)
    dataset.status = DatasetStatus.READY.value
    dataset.error_message = None
    session.commit()
    session.refresh(dataset)
    return dataset
