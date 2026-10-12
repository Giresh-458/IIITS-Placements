import pytest
import json
import asyncio
from datetime import datetime
from src.crawler.engine import CrawlerEngine
from src.extraction.event_extractor import extract_event_candidate
from src.extraction.date_normalizer import parse_date_with_context

@pytest.mark.asyncio
async def test_crawler_engine_limits():
    seeds = [{"institution": "Test", "seed_url": "http://example.com", "source_category": "P0_DIRECT_EVENT_FEED"}]
    engine = CrawlerEngine(seeds, max_pages=1, max_depth=1)
    
    events, telemetry = await engine.run()
    assert telemetry.sources_attempted == 1
    assert telemetry.sources_succeeded >= 0

def test_extract_event_candidate_basic():
    html = "<html><body>Campus Recruitment Drive by TechCorp on 10 Oct 2026. Role: SDE. CTC: 12 LPA. Batch 2026. Branches: CSE, IT</body></html>"
    text = "Campus Recruitment Drive by TechCorp on 10 Oct 2026. Role: SDE. CTC: 12 LPA. Batch 2026. Branches: CSE, IT"
    cand = extract_event_candidate(html, text, "http://example.com/event", {"institution": "Test"})
    assert cand is not None
    assert cand.company_name == "TechCorp"
    assert cand.role == "SDE"
    assert cand.ctc_raw == "12 LPA"
    assert cand.ctc_raw == "12 LPA"
    assert cand.batch == "2026 batch"

def test_date_normalizer_extraction():
    d, conf = parse_date_with_context("28th September", "2026-10-04", datetime(2026, 10, 4))
    assert d.year == 2026
    assert d.month == 9
    assert d.day == 28
    
    d, conf = parse_date_with_context("28 September 2026", "", datetime(2026, 10, 4))
    assert d.year == 2026

def test_extract_event_candidate_missing_optional():
    html = "<html><body>Campus Recruitment Drive by TechCorp. Drive Date: 12-10-2026</body></html>"
    text = "Campus Recruitment Drive by TechCorp. Drive Date: 12-10-2026"
    cand = extract_event_candidate(html, text, "http://example.com/event", {"institution": "Test"})
    assert cand is not None
    assert cand.company_name == "TechCorp"
    assert cand.ctc is None
    assert cand.role is None
    
def test_extract_event_candidate_false_positive():
    html = "<html><body>Recruitment procedure for companies.</body></html>"
    text = "Recruitment procedure for companies."
    cand = extract_event_candidate(html, text, "http://example.com/event", {"institution": "Test"})
    assert cand is None
