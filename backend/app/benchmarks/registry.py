from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.benchmarks.text_quick_check import TEXT_QUICK_CHECK, TextSample


class BenchmarkPlugin(Protocol):
    manifest: dict[str, object]

    def samples(self, sample_limit: int | None) -> tuple[TextSample, ...]: ...


@dataclass(frozen=True, slots=True)
class TextQuickCheckPlugin:
    manifest: dict[str, object]

    def samples(self, sample_limit: int | None) -> tuple[TextSample, ...]:
        return TEXT_QUICK_CHECK.samples[:sample_limit]


TEXT_QUICK_CHECK_PLUGIN = TextQuickCheckPlugin(
    manifest={
        "benchmark_id": TEXT_QUICK_CHECK.identifier,
        "version": TEXT_QUICK_CHECK.version,
        "display_name": TEXT_QUICK_CHECK.display_name,
        "description": "A small deterministic text benchmark for endpoint verification.",
        "modalities": ["text"],
        "required_capabilities": ["text_input"],
        "scoring": {"type": "exact_match"},
        "sample_count": len(TEXT_QUICK_CHECK.samples),
        "datasets": [],
    }
)

BUILTIN_PLUGINS: tuple[BenchmarkPlugin, ...] = (TEXT_QUICK_CHECK_PLUGIN,)


def get_installed_plugin(benchmark_id: str, version: str) -> BenchmarkPlugin | None:
    return next(
        (
            plugin
            for plugin in BUILTIN_PLUGINS
            if plugin.manifest["benchmark_id"] == benchmark_id and plugin.manifest["version"] == version
        ),
        None,
    )
