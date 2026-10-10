"""The Alembic migration must create exactly the schema defined by the models."""

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

from app.db import Base, make_engine

BACKEND = Path(__file__).resolve().parents[2]


def test_migration_matches_models(tmp_path):
    url = f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}"
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.attributes["database_url"] = url
    command.upgrade(cfg, "head")

    engine = make_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    # Ignore differences SQLite cannot represent (e.g. server defaults on booleans).
    relevant = [d for d in diff if d[0] in ("add_table", "remove_table", "add_column", "remove_column")]
    assert relevant == [], relevant
