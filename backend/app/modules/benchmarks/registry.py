from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.benchmarks import BUILTIN_PLUGINS, register_manifest_plugin
from app.db.models import BenchmarkDefinition


def ensure_builtin_benchmark_definitions(session: Session) -> None:
    """Register built-in manifests idempotently on application startup."""

    for plugin in BUILTIN_PLUGINS:
        manifest = plugin.manifest
        definition = session.scalar(
            select(BenchmarkDefinition).where(
                BenchmarkDefinition.benchmark_id == manifest["benchmark_id"],
                BenchmarkDefinition.version == manifest["version"],
            )
        )
        if definition is None:
            session.add(
                BenchmarkDefinition(
                    benchmark_id=str(manifest["benchmark_id"]),
                    version=str(manifest["version"]),
                    display_name=str(manifest["display_name"]),
                    status="available",
                    manifest=manifest,
                    source="builtin",
                )
            )
    session.commit()
    for definition in session.scalars(select(BenchmarkDefinition)):
        register_manifest_plugin(definition.manifest)
