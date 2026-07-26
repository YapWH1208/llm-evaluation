from __future__ import annotations

import argparse
import json
from typing import Sequence

from app.core.config import Settings
from app.db.database import Database, DatabaseValidationError
from app.db.mongo import MongoConfigurationError, MongoDocumentStore, MongoValidationError


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LLM/SLM Evaluation Platform database operations")
    subparsers = parser.add_subparsers(dest="command", required=True)
    database = subparsers.add_parser("database", help="Inspect or initialize the configured database")
    database.add_argument("action", choices=("initialize", "preview", "validate"))
    arguments = parser.parse_args(argv)

    settings = Settings.from_environment()
    configured_database: Database | MongoDocumentStore | None = None
    try:
        configured_database = (
            MongoDocumentStore(settings) if settings.database_kind == "mongodb" else Database(settings)
        )
        if arguments.action == "preview":
            pending = configured_database.migration_preview()
            print(json.dumps([{"version": item.version, "id": item.migration_id, "description": item.description} for item in pending], indent=2))
            return 0
        if arguments.action == "validate":
            try:
                validation = configured_database.initialize("validate")
            except (DatabaseValidationError, MongoValidationError) as error:
                print(str(error))
                return 1
        else:
            validation = configured_database.initialize("auto_migrate")
        assert not isinstance(validation, tuple)
        print(json.dumps({"database": validation.database_kind, "schema_version": validation.current_version, "valid": validation.is_valid}, indent=2))
        return 0
    except MongoConfigurationError as error:
        print(str(error))
        return 1
    finally:
        if isinstance(configured_database, MongoDocumentStore):
            configured_database.close()
        elif configured_database is not None:
            configured_database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
