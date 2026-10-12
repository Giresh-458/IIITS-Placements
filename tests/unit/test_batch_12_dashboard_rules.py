import pytest
from datetime import datetime, timedelta
from src.classification.business_rules import classify_event
from src.models.domain import NormalizedHiringEvent

def test_temporal_status_mapping():
    base_date = datetime(2026, 10, 5)
    
    # 1. UPCOMING -> ACTIVE_OPPORTUNITY
    ev = NormalizedHiringEvent(event_id="1", event_date="2026-10-10", institution="X", source_seed_url="http://x")
    res = classify_event(ev, as_of=base_date)
    assert res.currentness == "UPCOMING"
    assert res.temporal_status == "ACTIVE_OPPORTUNITY"
    
    # 2. ONGOING -> ACTIVE_OPPORTUNITY
    ev = NormalizedHiringEvent(event_id="2", event_date="2026-10-05", institution="X", source_seed_url="http://x")
    res = classify_event(ev, as_of=base_date)
    assert res.currentness == "ONGOING"
    assert res.temporal_status == "ACTIVE_OPPORTUNITY"
    
    # 3. REGISTRATION_OPEN -> ACTIVE_OPPORTUNITY
    ev = NormalizedHiringEvent(event_id="3", registration_deadline="2026-10-10", institution="X", source_seed_url="http://x")
    res = classify_event(ev, as_of=base_date)
    assert res.currentness == "REGISTRATION_OPEN"
    assert res.temporal_status == "ACTIVE_OPPORTUNITY"
    
    # 4. COMPLETED_RECENT -> HOT_OUTREACH_LEAD (15-day rule)
    ev = NormalizedHiringEvent(event_id="4", event_date="2026-09-25", institution="X", source_seed_url="http://x")
    res = classify_event(ev, as_of=base_date)
    assert res.currentness == "COMPLETED_RECENT"
    assert res.temporal_status == "HOT_OUTREACH_LEAD"
    
    # 5. COMPLETED_OLD -> STALE
    ev = NormalizedHiringEvent(event_id="5", event_date="2026-09-10", institution="X", source_seed_url="http://x")
    res = classify_event(ev, as_of=base_date)
    assert res.currentness == "COMPLETED_OUTSIDE_15_DAY_WINDOW"
    assert res.temporal_status == "STALE"
    
    # 6. UNKNOWN -> UNKNOWN
    ev = NormalizedHiringEvent(event_id="6", institution="X", source_seed_url="http://x")
    res = classify_event(ev, as_of=base_date)
    assert res.currentness == "UNKNOWN"
    assert res.temporal_status == "UNKNOWN"

def test_15_day_boundary():
    base_date = datetime(2026, 10, 20)
    
    # today - 16 days -> NOT HOT (STALE)
    ev_16 = NormalizedHiringEvent(event_id="16", event_date="2026-10-04", institution="X", source_seed_url="http://x")
    res_16 = classify_event(ev_16, as_of=base_date)
    assert res_16.temporal_status == "STALE"
    
    # today - 15 days -> HOT
    ev_15 = NormalizedHiringEvent(event_id="15", event_date="2026-10-05", institution="X", source_seed_url="http://x")
    res_15 = classify_event(ev_15, as_of=base_date)
    assert res_15.temporal_status == "HOT_OUTREACH_LEAD"
    
    # today - 14 days -> HOT
    ev_14 = NormalizedHiringEvent(event_id="14", event_date="2026-10-06", institution="X", source_seed_url="http://x")
    res_14 = classify_event(ev_14, as_of=base_date)
    assert res_14.temporal_status == "HOT_OUTREACH_LEAD"
