import pytest

from src.extraction.event_extractor import extract_candidates_from_pages, extract_event_candidate
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


def test_detail_extraction_ignores_unrelated_post_content():
    html = """
    <html><body>
      <article class="post">
        <h1>Almighty Auto Ancillary Pvt. Ltd final result declared</h1>
        <div class="entry-content">
          Dear Students. Please find the selected students list and offer letter below.
          Name, latest qualification, branch.
        </div>
      </article>
      <section class="related-posts">
        <h3>Reliance Is Hiring B.Tech graduates</h3>
        <p>Company: Reliance Industries Limited (RIL). Role: GET. CTC: 9.5 LPA.</p>
      </section>
    </body></html>
    """
    candidate = extract_event_candidate(
        html,
        "Almighty Auto Ancillary final result; Reliance Industries Limited is hiring; CTC 9.5 LPA",
        "https://trident.ac.in/placementnotice/almighty-auto-ancillary-pvt-ltd-final-result",
        {"institution": "Trident Academy of Technology", "seed_url": "https://trident.ac.in/placementnotice"},
    )

    assert candidate is None


def test_detail_extraction_uses_primary_article_not_related_hiring_post():
    html = """
    <html><body>
      <article class="post">
        <h1>Reliance is hiring engineering graduates</h1>
        <div class="entry-content">
          Dear Students. Reliance Industries Limited is hiring 2027 engineering graduates.
          Company: Reliance Industries Limited (RIL).
          Role: Graduate Engineer Trainee (GET). CTC: 9.5 LPA.
          Register before 23 October 2026.
        </div>
      </article>
      <section class="related-posts">
        <h3>Almighty Auto Ancillary final result declared</h3>
        <p>Selected students list and offer letter issued.</p>
      </section>
    </body></html>
    """
    candidate = extract_event_candidate(
        html,
        "Reliance is hiring engineering graduates. Related: Almighty Auto Ancillary final result.",
        "https://trident.ac.in/placementnotice/reliance-is-hiring",
        {"institution": "Trident Academy of Technology", "seed_url": "https://trident.ac.in/placementnotice"},
    )

    assert candidate is not None
    assert "Reliance" in candidate.company_name
    assert "Almighty" not in candidate.company_name
    assert "Graduate Engineer Trainee" in candidate.role


def test_archive_page_with_multiple_notices_is_not_one_event_candidate():
    html = """
    <html><body>
      <main class="entry-content">
        <h1>Recent Notices</h1>
        <article><h3><a href="/placementnotice/reliance-is-hiring">Reliance is hiring engineering graduates</a></h3>
          Reliance Industries Limited is hiring. Role: GET. CTC: 9.5 LPA.</article>
        <article><h3><a href="/placementnotice/almighty-final-result">Almighty Auto Ancillary final result declared</a></h3>
          Selected students list and offer letter issued.</article>
        <article><h3><a href="/placementnotice/itc-campus-recruitment">ITC Limited Campus Recruitment Drive</a></h3>
          Registration and online test details.</article>
      </main>
    </body></html>
    """
    candidate = extract_event_candidate(
        html,
        "Recent Notices Reliance hiring Almighty final result ITC Campus Recruitment Drive",
        "https://trident.ac.in/placementnotice",
        {"institution": "Trident Academy of Technology", "seed_url": "https://trident.ac.in/placementnotice"},
    )

    assert candidate is None
