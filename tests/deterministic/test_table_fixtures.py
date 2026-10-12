import pytest
from tests.deterministic.conftest import extract_from_file
from src.storage.database import DatabaseManager

@pytest.fixture
def db_manager():
    return DatabaseManager("sqlite:///:memory:")

@pytest.mark.asyncio
async def test_table_fixture(db_manager):
    ev = extract_from_file('event_table.html', folder='tables')
    assert ev is not None
    assert "DH Bars" in ev.company_name
