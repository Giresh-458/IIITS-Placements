import pytest
from src.config.settings import Settings
from src.models.domain import College, HiringEvent, SourceProfile
from src.models.enums import InstitutionType, CampusEventType, SourceAccessClassification
from src.orchestration.state import create_initial_state
from src.telemetry.models import CrawlRun
from datetime import datetime

def test_settings_load():
    settings = Settings()
    assert settings.crawl_budget.max_runtime_seconds > 0
    assert settings.eligibility.cse_min_lpa == 10.0

def test_college_model():
    college = College(name="IIIT Sri City", institution_type=InstitutionType.IIIT, is_target_profile=True)
    assert college.name == "IIIT Sri City"
    assert college.institution_type == InstitutionType.IIIT
    assert college.is_target_profile is True

def test_hiring_event_model():
    event = HiringEvent(campus_type=CampusEventType.ON_CAMPUS)
    assert event.campus_type == CampusEventType.ON_CAMPUS
    assert event.event_status.value == "UNKNOWN"

def test_source_profile_model():
    profile = SourceProfile(access_status=SourceAccessClassification.PUBLIC_STATIC_HTML)
    assert profile.access_status == SourceAccessClassification.PUBLIC_STATIC_HTML
    assert profile.requires_browser is False

def test_initial_state():
    state = create_initial_state(run_id="run_123", sources=[{"url": "http://example.com"}])
    assert state["run_id"] == "run_123"
    assert state["sources"][0]["url"] == "http://example.com"

def test_crawl_run_telemetry():
    run = CrawlRun(run_id="run_123", start_time=datetime.utcnow())
    assert run.run_id == "run_123"
    assert run.urls_attempted == 0
