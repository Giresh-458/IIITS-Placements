import pytest
import os
from bs4 import BeautifulSoup
from src.extraction.event_extractor import extract_event_candidate
from src.orchestration.state import create_initial_state
from src.storage.database import DatabaseManager
from tests.deterministic.conftest import extract_from_file

@pytest.fixture
def db_manager():
    return DatabaseManager("sqlite:///:memory:")

@pytest.mark.asyncio
async def test_full_html_fixture(db_manager):
    ev = extract_from_file('event_full.html')
    
    assert ev is not None
    assert "TechCorp Solutions" in ev.company_name
    assert "Software Engineer" in ev.role
    assert "12 LPA" in ev.ctc_raw or "12" in ev.ctc_raw
    assert "CSE" in ev.eligible_branches
    assert "IT" in ev.eligible_branches
    assert "ECE" in ev.eligible_branches
    
    state = create_initial_state()
    from src.orchestration.normalization_adapter import normalize_candidates
    norm_events = normalize_candidates([ev])
    state["normalized_events"] = [e.model_dump(mode='json') for e in norm_events]
    assert len(norm_events) == 1
    ne = norm_events[0]
    
    assert ne.company_name == "TechCorp Solutions Private Limited"
    assert ne.role == "SOFTWARE_ENGINEERING"
    assert ne.ctc == 12.0

@pytest.mark.asyncio
async def test_missing_optional_fixture(db_manager):
    ev = extract_from_file('event_missing_optional.html')
    
    assert ev is not None
    assert "Acme Corp" in ev.company_name
    assert "Data Analyst" in ev.role
    
    state = create_initial_state()
    from src.orchestration.normalization_adapter import normalize_candidates
    norm_events = normalize_candidates([ev])
    state["normalized_events"] = [e.model_dump(mode='json') for e in norm_events]
    assert len(norm_events) == 1
    ne = norm_events[0]
    
    assert ne.company_name == "Acme Corp"
    assert ne.ctc is None
    assert ne.eligible_branches == []

@pytest.mark.asyncio
async def test_negative_fixture(db_manager):
    ev = extract_from_file('event_negative.html')
    
    if ev is None:
        assert True
        return
        
    state = create_initial_state()
    from src.orchestration.normalization_adapter import normalize_candidates
    norm_events = normalize_candidates([ev])
    
    if norm_events:
        assert norm_events[0].event_status == "REJECTED_NON_EVENT"
    else:
        assert True
