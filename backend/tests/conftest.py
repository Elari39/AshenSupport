import os
import tempfile
from pathlib import Path

import pytest

# PG tests run only against an explicitly designated disposable test database.
test_folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["ASHEN_DATABASE_URL"] = os.environ.get(
    "ASHEN_TEST_DATABASE_URL", "sqlite:///" + str(Path(test_folder.name) / "test.db")
)
if os.environ.get("ASHEN_TEST_DATABASE_URL"):
    from sqlalchemy.engine import make_url

    if not (make_url(os.environ["ASHEN_TEST_DATABASE_URL"]).database or "").endswith("_test"):
        raise RuntimeError("Destructive integration tests require a database ending in _test")
os.environ["ASHEN_PROVIDER"] = "fake"
os.environ["ASHEN_ORIGIN"] = "http://testserver"

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def database():
    if engine.dialect.name == "postgresql":
        from sqlalchemy import text

        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    from app.db import Project

    with SessionLocal.begin() as db:
        db.add_all(
            [
                Project(id="notes-of-ashen", name="Notes of Ashen"),
                Project(id="ashen-courier", name="AshenCourier"),
            ]
        )
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        response = client.post("/api/v1/sessions/guest")
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        yield client
