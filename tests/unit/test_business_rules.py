import pytest
from datetime import datetime
from src.classification.business_rules import classify_event
from src.models.domain import NormalizedHiringEvent

def test_hot_outreach_lead_definition():
    # Only completed campus hiring event within the previous 15 days is HOT.
    # High CTC does not make an event HOT.
    
    # 5 days ago -> HOT
    ev = NormalizedHiringEvent(event_id="1", institution="A", event_date="2026-09-30")
    res = classify_event(ev, as_of=datetime(2026, 10, 5))
    assert res.currentness == "COMPLETED_RECENT"
    assert res.temporal_status == "HOT_OUTREACH_LEAD"
    assert res.target_fit == "REVIEW"
    
    # Exactly 15 days ago -> HOT
    ev = NormalizedHiringEvent(event_id="2", institution="A", event_date="2026-09-20")
    res = classify_event(ev, as_of=datetime(2026, 10, 5))
    assert res.currentness == "COMPLETED_RECENT"
    assert res.temporal_status == "HOT_OUTREACH_LEAD"
    assert res.target_fit == "REVIEW"
    
    # 16 days ago -> STALE (FILTERED_OUT)
    ev = NormalizedHiringEvent(event_id="3", institution="A", event_date="2026-09-19")
    res = classify_event(ev, as_of=datetime(2026, 10, 5))
    assert res.currentness == "COMPLETED_OUTSIDE_15_DAY_WINDOW"
    assert res.temporal_status == "STALE"
    assert res.target_fit == "FILTERED_OUT"
    
    # upcoming event -> ACTIVE
    ev = NormalizedHiringEvent(event_id="4", institution="A", event_date="2026-10-06")
    res = classify_event(ev, as_of=datetime(2026, 10, 5))
    assert res.currentness == "UPCOMING"
    assert res.temporal_status == "ACTIVE_OPPORTUNITY"
    
    # registration still open -> ACTIVE
    ev = NormalizedHiringEvent(event_id="5", institution="A", registration_deadline="2026-10-06")
    res = classify_event(ev, as_of=datetime(2026, 10, 5))
    assert res.currentness == "REGISTRATION_OPEN"
    assert res.temporal_status == "ACTIVE_OPPORTUNITY"
    
    # ongoing -> ACTIVE
    ev = NormalizedHiringEvent(event_id="6", institution="A", event_date="2026-10-05")
    res = classify_event(ev, as_of=datetime(2026, 10, 5))
    assert res.currentness == "ONGOING"
    assert res.temporal_status == "ACTIVE_OPPORTUNITY"
    
    # high CTC + old event -> STALE
    ev = NormalizedHiringEvent(event_id="7", institution="A", event_date="2026-09-01", ctc=15.0, eligible_branches=["CSE"])
    res = classify_event(ev, as_of=datetime(2026, 10, 5))
    assert res.currentness == "COMPLETED_OUTSIDE_15_DAY_WINDOW"
    assert res.temporal_status == "STALE"
    
    # high CTC + upcoming event -> NOT HOT, ACTIVE
    ev = NormalizedHiringEvent(event_id="8", institution="A", event_date="2026-10-10", ctc=15.0, eligible_branches=["CSE"])
    res = classify_event(ev, as_of=datetime(2026, 10, 5))
    assert res.currentness == "UPCOMING"
    assert res.temporal_status == "ACTIVE_OPPORTUNITY"

def test_package_threshold_examples():
    # EEE + 3.52 LPA + tech role + fresher -> NOT_QUALIFIED package -> FILTERED_OUT
    ev = NormalizedHiringEvent(event_id="0", institution="A", eligible_branches=["EEE"], ctc=3.52, role_family="SOFTWARE_ENGINEERING", graduation_year=2026)
    res = classify_event(ev)
    assert res.package_qualification == "NOT_QUALIFIED"
    assert res.target_fit == "FILTERED_OUT"

    # CSE thresholds
    # CSE + 9.99 LPA -> NOT CSE-qualified
    ev = NormalizedHiringEvent(event_id="1", institution="A", eligible_branches=["CSE"], ctc=9.99, role_family="SOFTWARE_ENGINEERING", graduation_year=2026)
    res = classify_event(ev)
    assert res.package_qualification == "NOT_QUALIFIED"
    assert res.target_fit == "FILTERED_OUT"
    
    # CSE + 10.00 LPA -> CSE-qualified
    ev = NormalizedHiringEvent(event_id="2", institution="A", eligible_branches=["CSE"], ctc=10.00, role_family="SOFTWARE_ENGINEERING", graduation_year=2026)
    res = classify_event(ev)
    assert res.package_qualification == "QUALIFIED_CSE"
    assert res.target_fit == "QUALIFIED"
    
    # CSE + 10.01 LPA -> CSE-qualified
    ev = NormalizedHiringEvent(event_id="3", institution="A", eligible_branches=["CSE"], ctc=10.01, role_family="SOFTWARE_ENGINEERING", graduation_year=2026)
    res = classify_event(ev)
    assert res.package_qualification == "QUALIFIED_CSE"
    assert res.target_fit == "QUALIFIED"
    
    # ECE + 6.49 LPA -> NOT ECE-qualified
    ev = NormalizedHiringEvent(event_id="4", institution="A", eligible_branches=["ECE"], ctc=6.49, role_family="SOFTWARE_ENGINEERING", graduation_year=2026)
    res = classify_event(ev)
    assert res.package_qualification == "NOT_QUALIFIED"
    assert res.target_fit == "FILTERED_OUT"
    
    # ECE + 6.50 LPA -> ECE-qualified
    ev = NormalizedHiringEvent(event_id="5", institution="A", eligible_branches=["ECE"], ctc=6.50, role_family="SOFTWARE_ENGINEERING", graduation_year=2026)
    res = classify_event(ev)
    assert res.package_qualification == "QUALIFIED_ECE"
    assert res.target_fit == "QUALIFIED"
    
    # ECE + 6.51 LPA -> ECE-qualified
    ev = NormalizedHiringEvent(event_id="6", institution="A", eligible_branches=["ECE"], ctc=6.51, role_family="SOFTWARE_ENGINEERING", graduation_year=2026)
    res = classify_event(ev)
    assert res.package_qualification == "QUALIFIED_ECE"
    assert res.target_fit == "QUALIFIED"
    
    # UNKNOWN branch + high CTC -> package qualification UNKNOWN, not QUALIFIED target fit
    ev = NormalizedHiringEvent(event_id="7", institution="A", eligible_branches=[], ctc=20.0, role_family="SOFTWARE_ENGINEERING", graduation_year=2026)
    res = classify_event(ev)
    assert res.package_qualification == "UNKNOWN"
    assert res.target_fit == "REVIEW"

def test_unknown_evidence_is_not_true():
    # role = UNKNOWN -> technology relevance = UNKNOWN
    ev = NormalizedHiringEvent(event_id="1", institution="A", role_family="UNKNOWN")
    assert classify_event(ev).role_relevance == "UNKNOWN"
    
    # batch = UNKNOWN -> fresher scope = UNKNOWN
    ev = NormalizedHiringEvent(event_id="2", institution="A")
    assert classify_event(ev).fresher_scope == "UNKNOWN"

def test_past_registration_deadline_unknown_event_date():
    # registration_deadline < today AND event_date = UNKNOWN -> UNKNOWN currentness, NOT COMPLETED
    ev = NormalizedHiringEvent(event_id="1", institution="A", registration_deadline="2026-09-01")
    res = classify_event(ev, as_of=datetime(2026, 10, 5))
    assert res.currentness == "UNKNOWN"
    assert res.temporal_status == "UNKNOWN"
    assert res.target_fit == "REVIEW"

def test_adversarial_business_tests():
    # unknown branch + high CTC -> UNKNOWN package qual
    ev = NormalizedHiringEvent(event_id="1", institution="A", ctc=20.0, eligible_branches=[])
    assert classify_event(ev).package_qualification == "UNKNOWN"
    
    # unknown role + active date
    ev = NormalizedHiringEvent(event_id="2", institution="A", event_date="2026-10-06", role_family="UNKNOWN")
    res = classify_event(ev, as_of=datetime(2026, 10, 5))
    assert res.role_relevance == "UNKNOWN"
    assert res.currentness == "UPCOMING"
    assert res.temporal_status == "ACTIVE_OPPORTUNITY"
    
    # low CTC + recent completed event -> NOT_QUALIFIED package but temporal is HOT
    ev = NormalizedHiringEvent(event_id="3", institution="A", ctc=3.0, eligible_branches=["CSE"], event_date="2026-09-30")
    res = classify_event(ev, as_of=datetime(2026, 10, 5))
    assert res.package_qualification == "NOT_QUALIFIED"
    assert res.currentness == "COMPLETED_RECENT"
    assert res.temporal_status == "HOT_OUTREACH_LEAD"
    assert res.target_fit == "FILTERED_OUT"
