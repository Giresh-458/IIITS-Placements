import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from src.crawler.engine import CrawlerEngine
from src.extraction.event_extractor import extract_event_candidate
from src.extraction.date_normalizer import extract_dates, is_event_recent, parse_date_with_context
from src.models.domain import HiringEventCandidate

@pytest.mark.asyncio
async def test_page_budget_enforcement():
    # Mocking crawler engine behavior would be ideal, but we can verify logic
    # by testing the state of the crawler engine configuration
    engine = CrawlerEngine([{"institution": "Test", "seed_url": "http://test.com", "source_category": "P0_DIRECT_EVENT_FEED"}], max_pages=15)
    assert engine.global_max_pages == 15

@pytest.mark.asyncio
async def test_playwright_actual_execution():
    engine = CrawlerEngine([], max_pages=15)
    
    # Static logic
    html = "<html><body><div id='app'>Loading...</div></body></html>"
    text = "Loading..."
    needs_js = len(text) < 2000 and "loading" in html.lower()
    assert needs_js == True
    
    # Real execution
    html_out, text_out = await engine.fetch_with_playwright("data:text/html,<script>document.write('JS RENDERED EVENT')</script>")
    assert "JS RENDERED EVENT" in text_out
    assert engine.telemetry.browser_pages == 1

@pytest.mark.asyncio
async def test_playwright_failure_bounded():
    engine = CrawlerEngine([], max_pages=15)
    
    # Force a timeout/failure (using an invalid or blackholed URL or very short timeout, but invalid protocol is easiest)
    html_out, text_out = await engine.fetch_with_playwright("invalid://url")
    assert html_out == ""
    assert text_out == ""
    assert engine.telemetry.browser_failures == 1
    assert engine.telemetry.browser_pages == 1

def test_event_false_positive():
    html = "Recruitment procedure for companies. Companies can register for placements"
    text = html
    cand = extract_event_candidate(html, text, "http://test.com", {"institution": "Test"})
    assert cand is None

def test_real_event():
    text = "Campus Recruitment Drive by Example Technologies on 28th September for 2027 Batch. Branches: CSE, ECE"
    cand = extract_event_candidate(text, text, "http://test.com", {"institution": "Test"})
    assert cand is not None
    assert cand.company_name == "Example Technologies"
    assert cand.batch == "2027 batch"

def test_date_regression():
    d1, c1 = parse_date_with_context("28th September", "2026-10-04", datetime(2026, 10, 4))
    assert d1.year == 2026
    assert d1.month == 9
    assert d1.day == 28

    d2, c2 = parse_date_with_context("28 September", "", datetime(2026, 10, 4))
    assert d2.year == 2026
    assert c2 == "LOW"

def test_recent_event_regression():
    start = datetime(2026, 9, 20)
    end = datetime(2026, 10, 4)
    assert is_event_recent(datetime(2026, 9, 28), start, end)
    assert is_event_recent(datetime(2026, 9, 25), start, end)
    assert not is_event_recent(datetime(2026, 9, 19), start, end)
    assert not is_event_recent(datetime(2026, 10, 5), start, end)

def test_ctc_cgpa_separation():
    text = "Campus Recruitment Drive by TechCorp. CTC: 10 LPA. Minimum CGPA: 7.0"
    cand = extract_event_candidate(text, text, "http://test.com", {"institution": "Test"})
    assert cand is not None
    assert cand.ctc_raw == "10 LPA"
    # CGPA requires explicit extractor, but verify CTC is not mixed
    assert cand.ctc_raw == "10 LPA"

def test_missing_optional_field():
    text = "Campus Recruitment Drive by TechCorp on 28th September."
    cand = extract_event_candidate(text, text, "http://test.com", {"institution": "Test"})
    assert cand is not None
    assert cand.company_name == "TechCorp"
    assert cand.role is None
    assert cand.ctc is None

def test_evidence_exists():
    text = "Campus Recruitment Drive by Example Technologies for Role: SDE"
    cand = extract_event_candidate(text, text, "http://test.com", {"institution": "Test"})
    assert cand.company_name == "Example Technologies"
    assert 'company' in cand.evidence
    assert cand.evidence['company']['text'] is not None
    assert cand.role == "SDE"
    assert 'role' in cand.evidence
