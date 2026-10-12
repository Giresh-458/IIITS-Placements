import pytest
from tests.deterministic.conftest import extract_from_file
from src.orchestration.state import create_initial_state
from src.storage.database import DatabaseManager

@pytest.fixture
def db_manager():
    return DatabaseManager("sqlite:///:memory:")

@pytest.mark.asyncio
async def test_duplicate_fixtures(db_manager):
    ev1 = extract_from_file('event_source1.html', folder='duplicates', inst='Inst1')
    ev2 = extract_from_file('event_source2.html', folder='duplicates', inst='Inst1')
    
    assert ev1 is not None
    assert ev2 is not None
    
    # Run both through normalization
    from src.orchestration.normalization_adapter import normalize_candidates
    norm_events = normalize_candidates([ev1, ev2])
    
    # Deduplication in normalization should merge them into ONE event
    assert len(norm_events) == 1
    ne = norm_events[0]
    
    assert ne.company_name == "TechCorp Solutions"
    assert ne.role == "SOFTWARE_ENGINEERING"
    assert ne.ctc == 12.0
    
    # It should have 2 source URLs
    assert len(ne.source_urls) == 2 or ne.canonical_identity is not None

@pytest.mark.asyncio
async def test_conflict_fixtures(db_manager):
    # What if two sources have conflicting CTC?
    # Source A: 10 LPA, Source B: 12 LPA
    ev1 = extract_from_file('event_source1.html', folder='duplicates', inst='Inst1')
    ev2 = extract_from_file('event_source2.html', folder='duplicates', inst='Inst1')
    ev1.ctc = 10.0
    ev1.ctc_raw = '10 LPA'
    import datetime
    ev1.discovered_at = datetime.datetime(2026, 10, 1)
    
    ev2.ctc = 12.0
    ev2.ctc_raw = '12 LPA'
    ev2.discovered_at = datetime.datetime(2026, 10, 2)
    
    from src.orchestration.normalization_adapter import normalize_candidates
    norm_events = normalize_candidates([ev1, ev2])
    assert len(norm_events) == 1
    ne = norm_events[0]
    
    # Since ev2 is FRESHER (Oct 2 > Oct 1), the conflict resolver should pick 12.0!
    assert ne.ctc == 12.0
    # And it should preserve the conflict in evidence
    assert any(ev.get("type") == "ctc_conflict" and ev.get("value") == 10.0 for ev in ne.evidence)
