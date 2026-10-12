import pytest
from src.orchestration.normalization_adapter import normalize_candidates

def test_failure_isolation():
    from src.models.domain import HiringEventCandidate
    
    # 1 good candidate, 1 completely malformed candidate that throws inside some logic if not isolated
    # Actually, normalization handles None fields gracefully.
    good = HiringEventCandidate(
        institution="Inst1",
        company_name="GoodCorp",
        role="SDE",
        ctc_raw="10 LPA",
        source_seed_url="http://test"
    )
    bad = HiringEventCandidate(
        institution="Inst1",
        company_name=None,
        role=None,
        ctc_raw=None,
        source_seed_url="http://test"
    )
    
    # If the adapter wasn't resilient, this would crash
    res = normalize_candidates([good, bad])
    
    # The bad one should be skipped (doesn't have any event data)
    # The good one should be processed
    assert len(res) == 1
    assert res[0].company_name == "GoodCorp"
