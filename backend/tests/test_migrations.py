from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from alembic import command
from app.db import Base, engine


def test_frozen_migration_matches_schema_and_is_repeatable():
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []
        assert "task_runs" in inspect(connection).get_table_names()
    command.downgrade(config, "base")
    assert "task_runs" not in inspect(engine).get_table_names()
