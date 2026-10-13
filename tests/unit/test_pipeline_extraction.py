import pytest

from src.extraction.event_extractor import extract_candidates_from_pages
from src.orchestration.pipeline import PipelineOrchestrator
from src.orchestration.state import create_initial_state


def _page(text, url="https://example.edu/event", institution="Test College"):
    return {
        "url": url,
        "seed_url": "https://example.edu/placements",
        "institution": institution,
        "html": f"<html><body>{text}</body></html>",
        "text": text,
        "depth": 0,
        "http_status": 200,
    }


@pytest.mark.asyncio
async def test_extraction_builds_candidates_from_crawled_pages():
    text = (
        "Campus Recruitment Drive by TechCorp on 10 Oct 2026. "
        "Role: SDE. CTC: 12 LPA. Batch 2026. Branches: CSE, IT"
    )
    state = create_initial_state()
    state["crawled_pages"] = [_page(text)]

    await PipelineOrchestrator()._do_extraction(state)

    assert len(state["raw_candidates"]) == 1
    candidate = state["raw_candidates"][0]
    assert candidate["institution"] == "Test College"
    assert candidate["company_name"] == "TechCorp"
    assert candidate["role"] == "SDE"
    assert candidate["ctc_raw"] == "12 LPA"
    assert candidate["event_url"] == "https://example.edu/event"
    assert state["telemetry"]["extraction_candidates"] == 1
    assert state["extraction_telemetry"] == {
        "pages_examined": 1,
        "candidates_found": 1,
        "candidates_by_source": {"Test College": 1},
        "pages_without_candidates": 0,
    }


@pytest.mark.asyncio
async def test_extraction_counts_non_event_pages_without_inventing_candidates():
    state = create_initial_state()
    state["crawled_pages"] = [
        _page("College home page and contact information", url="https://example.edu/"),
        _page("Admissions information", url="https://example.edu/admissions"),
    ]

    await PipelineOrchestrator()._do_extraction(state)

    assert state["raw_candidates"] == []
    assert state["telemetry"]["extraction_candidates"] == 0
    assert state["extraction_telemetry"]["pages_examined"] == 2
    assert state["extraction_telemetry"]["candidates_found"] == 0
    assert state["extraction_telemetry"]["pages_without_candidates"] == 2


@pytest.mark.asyncio
async def test_extraction_fails_closed_when_no_crawled_pages_are_available():
    state = create_initial_state()

    await PipelineOrchestrator()._safe_execute(
        state, "EXTRACTION", PipelineOrchestrator()._do_extraction
    )

    assert state["terminal_status"] == "FAILED"
    assert state["errors"][0]["stage"] == "EXTRACTION"
    assert "no crawled pages" in state["stop_reason"].lower()


def test_shared_extractor_rejects_malformed_page_records():
    with pytest.raises(ValueError, match="requires a URL"):
        extract_candidates_from_pages([{
            "institution": "Test College",
            "seed_url": "https://example.edu",
            "html": "<html></html>",
            "text": "",
        }])
