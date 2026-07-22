from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import Connection, inspect, text


@dataclass(frozen=True, slots=True)
class Migration:
    """A forward-only relational schema upgrade."""

    version: int
    migration_id: str
    description: str
    upgrade: Callable[[Connection], None]


def _add_column_if_missing(
    connection: Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    table_names = set(inspect(connection).get_table_names())
    if table_name not in table_names:
        return

    existing_columns = {column["name"] for column in inspect(connection).get_columns(table_name)}
    if column_name not in existing_columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}"))


def _upgrade_v2_prompt_package_reference(connection: Connection) -> None:
    """Preserve existing runs while adding the prompt package snapshot reference."""

    _add_column_if_missing(
        connection,
        "evaluation_runs",
        "prompt_package_id",
        "prompt_package_id VARCHAR(36)",
    )


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=2,
        migration_id="20260722_add_prompt_package_reference",
        description="Add prompt package references and register post-v1 platform tables.",
        upgrade=_upgrade_v2_prompt_package_reference,
    ),
)

LATEST_SCHEMA_VERSION = MIGRATIONS[-1].version
