import pytest
from src.models.domain import NormalizedHiringEvent
from src.classification.business_rules import classify_event
from datetime import datetime

def create_event_with_date(date_str: str) -> NormalizedHiringEvent:
    return NormalizedHiringEvent(
        event_id="test",
        institution="test",
        company_name="Test Corp",
        role_family="SOFTWARE_ENGINEERING",
        ctc=10.0,
        graduation_year=2026,
        event_date=date_str,
        event_date_raw=date_str,
        campus_mode="ON_CAMPUS"
    )

def test_status_boundaries():
    # Base date is 2026-10-05
    as_of = datetime(2026, 10, 5)
    
    # 16 days ago
    ev_16 = create_event_with_date("2026-09-19")
    cls_16 = classify_event(ev_16, as_of)
    assert cls_16.temporal_status == "STALE"
    
    # 15 days ago
    ev_15 = create_event_with_date("2026-09-20")
    cls_15 = classify_event(ev_15, as_of)
    assert cls_15.temporal_status == "HOT_OUTREACH_LEAD"
    
    # 14 days ago
    ev_14 = create_event_with_date("2026-09-21")
    cls_14 = classify_event(ev_14, as_of)
    assert cls_14.temporal_status == "HOT_OUTREACH_LEAD"
    
    # Future event
    ev_future = create_event_with_date("2026-10-10")
    cls_future = classify_event(ev_future, as_of)
    assert cls_future.temporal_status == "ACTIVE_OPPORTUNITY"
