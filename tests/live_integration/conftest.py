import os
import pytest
from src.config.settings import settings

@pytest.fixture
def live_db_url():
    """
    Returns the configured PostgreSQL connection string for live integration tests.
    Prioritizes LIVE_DATABASE_URL to ensure isolated test environments.
    """
    db_url = os.environ.get("LIVE_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url or "sqlite" in db_url:
        user = os.environ.get("POSTGRES_USER", "user")
        pwd = os.environ.get("POSTGRES_PASSWORD", "password")
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = os.environ.get("POSTGRES_PORT", "5432")
        dbname = os.environ.get("POSTGRES_DB", "placement_db")
        db_url = f"postgresql://{user}:{pwd}@{host}:{port}/{dbname}"
    return db_url.replace("postgresql+asyncpg://", "postgresql://")

@pytest.fixture
def live_api_url():
    """
    Returns the live API base URL for integration tests.
    """
    return os.environ.get("API_BASE_URL", "http://localhost:8000")
