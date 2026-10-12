import pytest
from src.crawler.engine import CrawlerEngine
from tests.deterministic.conftest import fixture_server

@pytest.mark.asyncio
async def test_dynamic_js_fixture(fixture_server):
    engine = CrawlerEngine(seeds=[])
    
    url = f"{fixture_server}/placement/dynamic/event_dynamic.html"
    
    # Prove that fetch_with_playwright correctly loads the dynamic content
    html, text = await engine.fetch_with_playwright(url)
    
    assert "TechCorp Solutions" in html
    assert "12 LPA" in html
    
    from src.extraction.event_extractor import extract_event_candidate
    from src.orchestration.normalization_adapter import normalize_candidates
    from src.classification.business_rules import classify_event
    
    ev = extract_event_candidate(html, text, url, {'institution': 'LocalTest', 'seed_url': url})
    assert ev is not None
    
    norm = normalize_candidates([ev])[0]
    assert norm.company_name == "TechCorp Solutions"
    assert norm.ctc == 12.0
    
    cls = classify_event(norm)
    assert cls.package_qualification == "QUALIFIED_CSE"

@pytest.mark.asyncio
async def test_dynamic_js_failure(fixture_server):
    engine = CrawlerEngine(seeds=[])
    
    # Provide an invalid port to simulate network failure in Playwright
    url = "http://127.0.0.1:1/does_not_exist.html"
    
    html, text = await engine.fetch_with_playwright(url)
    
    # Should return empty and record failure
    assert html == ""
    assert text == ""
    assert engine.telemetry.browser_failures == 1
