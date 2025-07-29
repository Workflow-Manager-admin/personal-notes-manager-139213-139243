import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Patch sys.path for module imports if needed.
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src/api")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../notes_database")))

from src.api.main import app, get_db
from models import Base

@pytest.fixture(scope="session")
def sqlite_url():
    """Fixture to provide a SQLite in-memory database URL for testing."""
    return "sqlite://"

@pytest.fixture(scope="session")
def engine(sqlite_url):
    """Fixture for a persistent in-memory SQLite engine for the test session."""
    return create_engine(
        sqlite_url, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

@pytest.fixture(scope="session")
def tables(engine):
    """Create tables for the test session and drop after done."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(engine, tables):
    """Provide a SQLAlchemy session for isolated test usage."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

@pytest.fixture
def client(db_session):
    """Fixture for FastAPI TestClient with test DB dependency override."""
    # Override dependency inside FastAPI app
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()

@pytest.fixture
def user_data():
    """Returns default user data for registration."""
    return {
        "username": "alice",
        "email": "alice@example.com",
        "password": "alicepassword123"
    }

@pytest.fixture
def second_user_data():
    """Returns a second user's data."""
    return {
        "username": "bob",
        "email": "bob@example.com",
        "password": "bobpassword456"
    }

def register_and_auth(client, username, email, password):
    """Helper for registering then logging in to get JWT token."""
    r1 = client.post("/auth/register", json={
        "username": username, "email": email, "password": password
    })
    assert r1.status_code == 200 or r1.status_code == 409

    r2 = client.post("/auth/login", data={
        "username": username, "password": password
    })
    assert r2.status_code == 200
    access_token = r2.json()["access_token"]
    return access_token

@pytest.fixture
def auth_header(client, user_data):
    """Returns {'Authorization': 'Bearer <token>'} for default user."""
    token = register_and_auth(client, user_data["username"], user_data["email"], user_data["password"])
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def second_auth_header(client, second_user_data):
    """Returns auth header for second user."""
    token = register_and_auth(client, second_user_data["username"], second_user_data["email"], second_user_data["password"])
    return {"Authorization": f"Bearer {token}"}
