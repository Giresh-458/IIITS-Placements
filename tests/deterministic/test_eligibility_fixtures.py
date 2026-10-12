import pytest
from tests.deterministic.conftest import extract_from_file
from src.storage.database import DatabaseManager

@pytest.fixture
def db_manager():
    return DatabaseManager("sqlite:///:memory:")

@pytest.mark.asyncio
async def test_eligibility_boundaries(db_manager):
    # Test boundary for CSE which should be >= 10 LPA according to rules
    ev_low = extract_from_file('event_boundary_low.html', folder='eligibility')
    ev_high = extract_from_file('event_boundary_high.html', folder='eligibility')
    
    assert ev_low is not None
    assert ev_high is not None
    
    from src.orchestration.normalization_adapter import normalize_candidates
    norm_low = normalize_candidates([ev_low])
    norm_high = normalize_candidates([ev_high])
    
    from src.classification.business_rules import classify_event
    
    cls_low = classify_event(norm_low[0])
    cls_high = classify_event(norm_high[0])
    
    # 9.99 should be rejected for CSE
    assert cls_low.package_qualification == "NOT_QUALIFIED"
    assert cls_low.target_fit == "FILTERED_OUT"
    
    # 10.0 should be qualified for CSE
    assert cls_high.package_qualification == "QUALIFIED_CSE"

@pytest.mark.asyncio
async def test_missing_branch(db_manager):
    ev = extract_from_file('event_missing_branch.html', folder='eligibility')
    assert ev is not None
    
    from src.orchestration.normalization_adapter import normalize_candidates
    norm = normalize_candidates([ev])
    
    from src.classification.business_rules import classify_event
    cls = classify_event(norm[0])
    
    # Branch is missing, package is 15 LPA. 
    # Should it be qualified? Without branch, we don't know if CSE/ECE fit.
    # The classification logic might set it to UNKNOWN or REVIEW.
    assert cls.package_qualification == "UNKNOWN"
    assert cls.package_qualification == "UNKNOWN"
    assert cls.target_fit == "REVIEW"

@pytest.mark.asyncio
async def test_batch_fixtures(db_manager):
    ev_fresher = extract_from_file('event_fresher.html', folder='eligibility')
    ev_wrong = extract_from_file('event_wrong_batch.html', folder='eligibility')
    ev_missing = extract_from_file('event_missing_batch.html', folder='eligibility')
    
    from src.orchestration.normalization_adapter import normalize_candidates
    norm_fresher = normalize_candidates([ev_fresher])[0]
    norm_wrong = normalize_candidates([ev_wrong])[0]
    norm_missing = normalize_candidates([ev_missing])[0]
    
    from src.classification.business_rules import classify_event
    
    cls_fresher = classify_event(norm_fresher)
    assert cls_fresher.fresher_scope == "TRUE"
    assert cls_fresher.target_fit == "QUALIFIED"
    
    cls_wrong = classify_event(norm_wrong)
    assert cls_wrong.fresher_scope == "FALSE"
    assert cls_wrong.target_fit == "FILTERED_OUT"
    
    cls_missing = classify_event(norm_missing)
    assert cls_missing.fresher_scope == "UNKNOWN"
    # Wait != automatically eligible, it becomes REVIEW
    assert cls_missing.target_fit == "REVIEW"
