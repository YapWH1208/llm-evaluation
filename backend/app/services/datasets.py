from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
from urllib.request import url2pathname

import httpx
from sqlalchemy.orm import Session

from app.db.models import DatasetStatus, DatasetVersion


class DatasetError(ValueError):
    pass


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
        return f"https://huggingface.co/{repository}/resolve/{quote(revision, safe='')}/{quote(relative_path, safe='/')}", headers
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return source_url, headers
    if parsed.scheme == "file":
        return Path(url2pathname(unquote(parsed.path))).resolve(), headers
    if not parsed.scheme:
        return Path(source_url).expanduser().resolve(), headers
    raise DatasetError("Dataset source must be HTTP(S), hf://owner/repository/path, file://, or a local file path.")


def write_dataset_source(source: Path | str, target: Path, headers: dict[str, str]) -> str:
    """Stream a configured source to a temporary file and return its SHA-256 digest."""

    digest = hashlib.sha256()
    if isinstance(source, Path):
        if not source.is_file():
            raise DatasetError("Dataset local source file was not found.")
        with source.open("rb") as input_file, target.open("wb") as output_file:
            for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                output_file.write(chunk)
                digest.update(chunk)
        return digest.hexdigest()
    with httpx.stream("GET", source, headers=headers, timeout=60, follow_redirects=True) as response:
        response.raise_for_status()
        with target.open("wb") as output_file:
            for chunk in response.iter_bytes():
                output_file.write(chunk)
                digest.update(chunk)
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
        actual_checksum = write_dataset_source(source, temporary, headers)
        dataset.status = DatasetStatus.VERIFYING.value; session.commit()
        if dataset.checksum and dataset.checksum.lower() != actual_checksum:
            temporary.unlink(missing_ok=True)
            raise DatasetError("Dataset checksum verification failed.")
        temporary.replace(target)
        dataset.checksum = actual_checksum; dataset.local_path = str(target); dataset.size_bytes = target.stat().st_size; dataset.status = DatasetStatus.READY.value
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
