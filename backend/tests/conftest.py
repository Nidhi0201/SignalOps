"""
Shared pytest fixtures for the SignalOps backend suite.

Tests run against REAL services, not mocks:
  * OpenSearch 2.11 in an ephemeral testcontainer (search/ingest paths)
  * Postgres 16 in an ephemeral testcontainer (alert-rule CRUD / SQLAlchemy)

The FastAPI app's two external dependencies -- `get_opensearch` and `get_db` --
are overridden to point at those containers. The background alert scheduler is
disabled via DISABLE_SCHEDULER so it never races the tests.
"""
import os

import pytest

# Must be set before importing the app so the startup hook (if it ever runs)
# does not spin up the APScheduler background job.
os.environ["DISABLE_SCHEDULER"] = "1"

from fastapi.testclient import TestClient  # noqa: E402
from opensearchpy import OpenSearch  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from testcontainers.opensearch import OpenSearchContainer  # noqa: E402
from testcontainers.postgres import PostgresContainer  # noqa: E402

LOGS_INDEX = "logs"

# Mapping mirrors app/main.py get_opensearch() so search behaves identically.
LOGS_MAPPING = {
    "mappings": {
        "properties": {
            "timestamp": {"type": "date"},
            "service": {"type": "keyword"},
            "level": {"type": "keyword"},
            "message": {"type": "text"},
            "trace_id": {"type": "keyword"},
            "metadata": {"type": "object", "enabled": True},
        }
    }
}


# --------------------------------------------------------------------------- #
# Containers (session-scoped: started once for the whole run)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def opensearch_client():
    with OpenSearchContainer(
        "opensearchproject/opensearch:2.11.0", security_enabled=False
    ) as container:
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(9200))
        client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_auth=None,
            use_ssl=False,
            verify_certs=False,
            timeout=30,
        )
        # Readiness: OpenSearchContainer waits for the port, but the cluster
        # can still be yellow briefly. A quick info() confirms it answers.
        client.info()
        yield client


@pytest.fixture(scope="session")
def db_engine():
    with PostgresContainer("postgres:16-alpine") as container:
        url = container.get_connection_url()  # psycopg2 driver by default
        os.environ["DATABASE_URL"] = url
        engine = create_engine(url)

        # Import models so their tables are registered on Base, then create.
        import app.models  # noqa: F401  (registers AlertRule + Incident)
        from app.database import Base

        Base.metadata.create_all(bind=engine)
        yield engine
        engine.dispose()


# --------------------------------------------------------------------------- #
# Per-test isolation
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _fresh_logs_index(opensearch_client):
    """Recreate the logs index before each test so no docs leak between tests."""
    if opensearch_client.indices.exists(index=LOGS_INDEX):
        opensearch_client.indices.delete(index=LOGS_INDEX)
    opensearch_client.indices.create(index=LOGS_INDEX, body=LOGS_MAPPING)
    yield


@pytest.fixture(autouse=True)
def _clean_db(db_engine):
    """Truncate Postgres tables between tests."""
    yield
    with db_engine.begin() as conn:
        conn.execute(text("TRUNCATE incidents, alert_rules RESTART IDENTITY CASCADE"))


# --------------------------------------------------------------------------- #
# App under test, wired to the containers
# --------------------------------------------------------------------------- #
@pytest.fixture
def client(opensearch_client, db_engine):
    from app.database import get_db
    from app.main import app, get_opensearch

    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def _override_opensearch():
        return opensearch_client

    def _override_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_opensearch] = _override_opensearch
    app.dependency_overrides[get_db] = _override_db

    # No context manager -> startup/shutdown lifespan does not run, so the
    # scheduler and create_all against the default engine stay dormant.
    yield TestClient(app)

    app.dependency_overrides.clear()


@pytest.fixture
def db_session(db_engine):
    """A SQLAlchemy session bound to the test Postgres, for inserting rows directly."""
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def seed_logs(client, opensearch_client):
    """
    Helper: POST logs through the real API, then refresh so they are
    immediately searchable (OpenSearch is near-real-time by default).
    Returns the created LogOut dicts.
    """
    def _seed(logs):
        resp = client.post("/logs/ingest", json=logs)
        assert resp.status_code == 200, resp.text
        opensearch_client.indices.refresh(index=LOGS_INDEX)
        return resp.json()

    return _seed
