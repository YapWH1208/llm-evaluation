from enum import StrEnum


class DatasetStatus(StrEnum):
    NOT_DOWNLOADED = "not_downloaded"
    WAITING = "waiting"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    PREPARING = "preparing"
    READY = "ready"
    UPDATE_AVAILABLE = "update_available"
    LICENSE_REQUIRED = "license_required"
    CREDENTIAL_REQUIRED = "credential_required"
    CORRUPTED = "corrupted"
    FAILED = "failed"
    REMOVING = "removing"
