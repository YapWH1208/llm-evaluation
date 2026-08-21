from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.benchmarks import (
    BUILTIN_PLUGINS,
    register_manifest_plugin,
    unregister_manifest_plugin,
    validate_manifest_plugin,
)
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.benchmarks.ports import BenchmarkRepository
from app.modules.benchmarks.scoring import ScoringError, validate_scoring_rule


class BenchmarkService:
    """Benchmark definition, version, and manifest behavior shared by all adapters."""

    def __init__(self, repository: BenchmarkRepository) -> None:
        self._repository = repository

    def list(self) -> list[Any]:
        return self._repository.list_definitions()

    def ensure_builtins(self) -> None:
        """Persist and register built-ins through the configured repository."""

        for plugin in BUILTIN_PLUGINS:
            manifest = plugin.manifest
            benchmark_id = str(manifest["benchmark_id"])
            version = str(manifest["version"])
            if self._repository.find_definition(benchmark_id, version) is None:
                self._repository.create_definitions(
                    [
                        {
                            "benchmark_id": benchmark_id,
                            "version": version,
                            "display_name": str(manifest["display_name"]),
                            "status": "available",
                            "manifest": manifest,
                            "source": "builtin",
                            "created_at": datetime.now(timezone.utc),
                        }
                    ]
                )
        for definition in self._repository.list_definitions():
            manifest = _value(definition, "manifest")
            if isinstance(manifest, dict):
                register_manifest_plugin(manifest)

    def register(self, payload: Any, *, source: str = "user") -> Any:
        manifest = _canonical_manifest(payload.benchmark_id, payload.version, payload.display_name, payload.manifest)
        created = self._repository.create_definitions(
            [
                {
                    "benchmark_id": payload.benchmark_id,
                    "version": payload.version,
                    "display_name": payload.display_name,
                    "manifest": manifest,
                    "status": "registered",
                    "source": source,
                    "created_at": datetime.now(timezone.utc),
                }
            ]
        )
        if created is None:
            raise ConflictError("Benchmark ID and version already exist")
        register_manifest_plugin(manifest)
        return created[0]

    def install_pack(self, payload: Any) -> list[Any]:
        keys = [(item.benchmark_id, item.version) for item in payload.benchmarks]
        if len(set(keys)) != len(keys):
            raise ConflictError("One or more benchmark versions already exist")
        manifests = [
            _canonical_manifest(item.benchmark_id, item.version, item.display_name, item.manifest)
            for item in payload.benchmarks
        ]
        values = [
            {
                "benchmark_id": item.benchmark_id,
                "version": item.version,
                "display_name": item.display_name,
                "manifest": manifest,
                "status": "registered",
                "source": f"pack:{payload.pack_name}",
                "created_at": datetime.now(timezone.utc),
            }
            for item, manifest in zip(payload.benchmarks, manifests, strict=True)
        ]
        installed = self._repository.create_definitions(values)
        if installed is None:
            raise ConflictError("One or more benchmark versions already exist")
        for manifest in manifests:
            register_manifest_plugin(manifest)
        return installed

    def get(self, definition_id: str) -> Any:
        item = self._repository.get_definition(definition_id)
        if item is None:
            raise NotFoundError("Benchmark definition not found", context={"definition_id": definition_id})
        return item

    def create_version(self, definition_id: str, payload: Any) -> Any:
        source = self.get(definition_id)
        benchmark_id = str(_value(source, "benchmark_id"))
        source_version = str(_value(source, "version"))
        source_name = str(_value(source, "display_name"))
        if payload.version == source_version:
            raise ValidationError("A new benchmark version is required for a content revision.")
        manifest = dict(payload.manifest)
        manifest_id = manifest.get("benchmark_id")
        if manifest_id is not None and manifest_id != benchmark_id:
            raise ValidationError("Manifest benchmark_id must match the source benchmark.")
        manifest.pop("benchmark_id", None)
        manifest.pop("version", None)
        display_name = payload.display_name or source_name
        canonical = _canonical_manifest(benchmark_id, payload.version, display_name, manifest)
        created = self._repository.create_definitions(
            [
                {
                    "benchmark_id": benchmark_id,
                    "version": payload.version,
                    "display_name": display_name,
                    "manifest": canonical,
                    "status": "registered",
                    "source": "revision",
                    "created_at": datetime.now(timezone.utc),
                }
            ]
        )
        if created is None:
            raise ConflictError("Benchmark ID and version already exist")
        register_manifest_plugin(canonical)
        return created[0]

    def prompt(self, definition_id: str) -> dict[str, Any]:
        benchmark = self.get(definition_id)
        manifest = _value(benchmark, "manifest", {})
        manifest = manifest if isinstance(manifest, dict) else {}
        return {
            "benchmark_id": _value(benchmark, "benchmark_id"),
            "version": _value(benchmark, "version"),
            "prompt": manifest.get("prompt"),
            "default_request_body": manifest.get("default_request_body", {}),
        }

    def dataset_status(self, definition_id: str) -> list[dict[str, Any]]:
        benchmark = self.get(definition_id)
        manifest = _value(benchmark, "manifest", {})
        declared = manifest.get("datasets", []) if isinstance(manifest, dict) else []
        items: list[dict[str, Any]] = []
        for descriptor in declared if isinstance(declared, list) else []:
            if not isinstance(descriptor, dict):
                continue
            dataset_id = descriptor.get("dataset_id") or descriptor.get("id")
            version = descriptor.get("version")
            if not isinstance(dataset_id, str):
                continue
            dataset = self._repository.find_dataset(dataset_id, version if isinstance(version, str) else None)
            items.append(
                {
                    "dataset_id": dataset_id,
                    "version": version,
                    "status": _value(dataset, "status", "not_registered") if dataset is not None else "not_registered",
                    "dataset_version_id": _value(dataset, "id") if dataset is not None else None,
                }
            )
        return items

    def update(self, definition_id: str, payload: Any) -> Any:
        existing = self.get(definition_id)
        values = payload.model_dump(exclude_unset=True)
        content_fields = {"display_name", "manifest"}.intersection(values)
        if _is_published(existing) and content_fields:
            raise ConflictError("Published benchmark content is immutable; create a new version instead.")
        if "manifest" in values:
            values["manifest"] = _canonical_manifest(
                str(_value(existing, "benchmark_id")),
                str(_value(existing, "version")),
                str(values.get("display_name") or _value(existing, "display_name")),
                values["manifest"],
            )
        updated = self._repository.update_definition(definition_id, values, require_registered=bool(content_fields))
        if updated is None:
            raise ConflictError("Published benchmark content is immutable; create a new version instead.")
        if "manifest" in values:
            unregister_manifest_plugin(str(_value(existing, "benchmark_id")), str(_value(existing, "version")))
            register_manifest_plugin(values["manifest"])
        return updated


class PromptPackageService:
    """Prompt package catalog and reference-integrity behavior."""

    def __init__(self, repository: BenchmarkRepository) -> None:
        self._repository = repository

    def create(self, payload: Any) -> Any:
        created = self._repository.create_prompt_package(
            {**payload.model_dump(), "created_at": datetime.now(timezone.utc)}
        )
        if created is None:
            raise ConflictError("Prompt package name and version already exist")
        return created

    def list(self) -> list[Any]:
        return self._repository.list_prompt_packages()

    def update(self, prompt_package_id: str, payload: Any) -> Any:
        existing = self._repository.get_prompt_package(prompt_package_id)
        if existing is None:
            raise NotFoundError("Prompt package not found", context={"prompt_package_id": prompt_package_id})
        duplicate = self._repository.find_prompt_package(payload.name, payload.version)
        if duplicate is not None and str(_value(duplicate, "id")) != prompt_package_id:
            raise ConflictError("Prompt package name and version already exist")
        updated = self._repository.update_prompt_package(prompt_package_id, payload.model_dump())
        if updated is None:
            raise ConflictError("Prompt package name and version already exist")
        return updated

    def delete(self, prompt_package_id: str) -> Any:
        item = self._repository.get_prompt_package(prompt_package_id)
        if item is None:
            raise NotFoundError("Prompt package not found", context={"prompt_package_id": prompt_package_id})
        if self._repository.prompt_run_reference_exists(prompt_package_id):
            raise ConflictError("Prompt package is referenced by an evaluation run")
        if any(_suite_references_prompt_package(suite, prompt_package_id) for suite in self._repository.list_suites()):
            raise ConflictError("Prompt package is referenced by an evaluation suite")
        if not self._repository.delete_prompt_package(prompt_package_id):
            raise NotFoundError("Prompt package not found", context={"prompt_package_id": prompt_package_id})
        return item


def _canonical_manifest(benchmark_id: str, version: str, display_name: str, source: dict[str, Any]) -> dict[str, Any]:
    manifest = dict(source)
    for field, expected in (("benchmark_id", benchmark_id), ("version", version), ("display_name", display_name)):
        value = manifest.get(field)
        if value is not None and value != expected:
            raise ValidationError(f"Manifest {field} must match the benchmark definition")
        manifest[field] = expected
    try:
        validate_manifest_plugin(manifest)
        scoring_rule = manifest.get("scoring")
        if scoring_rule is not None:
            if not isinstance(scoring_rule, dict):
                raise ScoringError("Benchmark scoring must be an object.")
            validate_scoring_rule(scoring_rule)
    except (ValueError, ScoringError) as error:
        raise ValidationError(str(error)) from error
    return manifest


def _is_published(definition: Any) -> bool:
    return str(_value(definition, "status")) != "registered" or str(_value(definition, "source")) == "builtin"


def _suite_references_prompt_package(suite: Any, prompt_package_id: str) -> bool:
    default_overrides = _value(suite, "default_prompt_overrides")
    if isinstance(default_overrides, dict) and any(value == prompt_package_id for value in default_overrides.values()):
        return True
    benchmark_list = _value(suite, "benchmark_list")
    return isinstance(benchmark_list, list) and any(
        isinstance(selection, dict) and selection.get("prompt_package_id") == prompt_package_id
        for selection in benchmark_list
    )


def _value(item: Any, key: str, default: Any = None) -> Any:
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)
