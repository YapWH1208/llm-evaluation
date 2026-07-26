from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.db.models import DatasetStatus, DatasetVersion


class DatasetError(ValueError):
    pass


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
    parsed = urlparse(dataset.source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise DatasetError("Dataset source URL must be HTTP or HTTPS.")
    if dataset.license_text and dataset.license_accepted_at is None:
        dataset.status = DatasetStatus.LICENSE_REQUIRED.value; session.commit()
        raise DatasetError("Dataset license must be accepted before download.")
    destination = Path(data_root).resolve() / "datasets" / dataset.dataset_id / dataset.version / dataset.revision
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / "dataset.bin"; temporary = destination / "dataset.part"
    dataset.status = DatasetStatus.DOWNLOADING.value; dataset.error_message = None; session.commit()
    digest = hashlib.sha256()
    try:
        with httpx.stream("GET", dataset.source_url, timeout=60, follow_redirects=True) as response:
            response.raise_for_status()
            with temporary.open("wb") as file:
                for chunk in response.iter_bytes():
                    file.write(chunk); digest.update(chunk)
        actual_checksum = digest.hexdigest()
        dataset.status = DatasetStatus.VERIFYING.value; session.commit()
        if dataset.checksum and dataset.checksum.lower() != actual_checksum:
            temporary.unlink(missing_ok=True)
            raise DatasetError("Dataset checksum verification failed.")
        temporary.replace(target)
        dataset.checksum = actual_checksum; dataset.local_path = str(target); dataset.status = DatasetStatus.READY.value
    except (httpx.HTTPError, OSError, DatasetError) as error:
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
    dataset.status = DatasetStatus.LICENSE_REQUIRED.value if dataset.license_text and dataset.license_accepted_at is None else DatasetStatus.NOT_DOWNLOADED.value
    dataset.error_message = None
    session.commit(); session.refresh(dataset)
    return dataset
