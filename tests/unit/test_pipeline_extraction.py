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


@pytest.mark.asyncio
async def test_pipeline_extraction_uses_article_scoped_dates_and_compensation():
    article_text = (
        "Campus Recruitment Drive by TechCorp. Interview Date: 10 Oct 2026. "
        "Role: SDE. CTC: 12 LPA."
    )
    page = _page(article_text, url="https://example.edu/placement/event")
    page["html"] = f"""
    <html><body>
      <article><div class="entry-content">{article_text}</div></article>
      <section class="related-posts">
        <p>Campus Recruitment Drive by OtherCorp. Interview Date: 23 Oct 2026. CTC: 40 LPA.</p>
      </section>
    </body></html>
    """
    page["text"] = (
        article_text
        + " Related: Campus Recruitment Drive by OtherCorp. "
        + "Interview Date: 23 Oct 2026. CTC: 40 LPA."
    )
    state = create_initial_state()
    state["crawled_pages"] = [page]

    await PipelineOrchestrator()._do_extraction(state)

    assert len(state["raw_candidates"]) == 1
    candidate = state["raw_candidates"][0]
    assert candidate["company_name"] == "TechCorp"
    assert candidate["ctc_raw"] == "12 LPA"
    assert candidate["event_date_raw"] == "10 Oct 2026"



def test_scoped_extraction_preserves_html_block_boundaries():
    html = """
    <html><head><title>Full Event Example</title></head><body>
      <h1>Campus Recruitment Drive by TechCorp Solutions Private Limited</h1>
      <p>Role: Software Engineer</p>
      <p>Location: Bangalore</p>
      <p>CTC: 12 LPA</p>
      <p>Eligible Branches: CSE, IT, ECE</p>
    </body></html>
    """
    candidate = extract_event_candidate(
        html,
        "flattened page text that may lack boundaries",
        "https://example.edu/event_full.html",
        {"institution": "Test College", "seed_url": "https://example.edu/placements"},
    )

    assert candidate is not None
    assert "TechCorp Solutions" in candidate.company_name
    assert "Software Engineer" in candidate.role
    assert candidate.ctc_raw == "12 LPA"


def test_main_scope_excludes_site_header_and_ignores_online_payment_navigation():
    html = """
    <html><body>
      <header class="site-header">
        <div>COUNSELLING CODE: 4680</div>
        <a href="/payments">ONLINE FEE PAYMENT</a>
        <a href="/login">STAFF LOGIN</a>
      </header>
      <main id="main-content">
        <h1>From Campus to Career: Transenergy Pvt. Ltd. Recruitment Drive</h1>
        <p>
          AAA College of Engineering and Technology successfully conducted a
          Campus Recruitment Drive by Transenergy Pvt. Ltd., Chennai, on
          10 October 2026 for final-year students.
        </p>
      </main>
    </body></html>
    """
    candidate = extract_event_candidate(
        html,
        "ONLINE FEE PAYMENT Transenergy Pvt. Ltd. Recruitment Drive",
        "https://aaaenggcoll.ac.in/from-campus-to-career-transenergy-pvt-ltd-recruitment-drive-on-10-10-2026",
        {
            "institution": "AAA College of Engineering & Technology",
            "seed_url": "https://aaaenggcoll.ac.in/placement/",
        },
    )

    assert candidate is not None
    assert candidate.company_name == "Transenergy Pvt. Ltd."
    assert candidate.campus_mode is None
    assert "ONLINE FEE PAYMENT" not in candidate.raw_text_excerpt
    assert "COUNSELLING CODE" not in candidate.raw_text_excerpt




def test_trident_detail_page_scopes_to_heading_article_and_extracts_berger_virtual_drive():
    html = """
    <html><body>
      <header><div class="site-title">Department of Training &amp; Placement</div></header>
      <main id="main">
        <article class="featured-post">
          <h1 class="entry-title">Berger Paints – GD Schedule &amp; Instructions: Virtual Campus Drive on (16th October 2026)</h1>
          <div class="post-content">
            <div class="entry-content">
              Dear Students. Please find below the schedule, meeting links, and important
              instructions for the Virtual Campus Drive scheduled on 16th October 2026.
              Join the virtual call individually from a laptop/desktop with an active camera.
            </div>
          </div>
        </article>
        <article class="related-post">
          <h2>Reliance Is Hiring Engineering Graduates</h2>
          <div class="post-content">
            <div class="entry-content">
              Company: Reliance Industries Limited
              Role: Graduate Engineer Trainee. CTC: 9.5 LPA.
            </div>
          </div>
        </article>
        <article class="related-post">
          <h2>Another placement result</h2>
          <div class="post-content"><div class="entry-content">Selected students list</div></div>
        </article>
      </main>
    </body></html>
    """
    page = _page(
        "flattened text that should not override the article HTML",
        url=(
            "https://trident.ac.in/placementnotice/"
            "berger-paints-gd-schedule-instructions-virtual-campus-drive-on-16th-october-2026"
        ),
        institution="Trident Academy of Technology",
    )
    page["html"] = html

    candidates = extract_candidates_from_pages([page])

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.company_name == "Berger Paints"
    assert candidate.campus_mode == "VIRTUAL"
    assert "Reliance Industries" not in candidate.raw_text_excerpt
    assert "Please find below the schedule" in candidate.raw_text_excerpt
    assert len(candidate.raw_text_excerpt) > 300
    assert candidate.event_date is not None
    assert candidate.event_date.strftime("%Y-%m-%d") == "2026-10-16"


def test_trident_archive_with_multiple_article_bodies_is_rejected():
    html = """
    <html><body>
      <h1 class="site-title">Department of Training &amp; Placement</h1>
      <main id="main">
        <article><h2>Berger Paints Virtual Campus Drive</h2>
          <div class="entry-content">Virtual Campus Drive scheduled on 16th October 2026.</div>
        </article>
        <article><h2>Reliance is hiring</h2>
          <div class="entry-content">Company: Reliance Industries Limited. Role: GET.</div>
        </article>
      </main>
    </body></html>
    """
    page = _page(
        "archive page",
        url="https://trident.ac.in/placementnotice",
        institution="Trident Academy of Technology",
    )
    page["html"] = html

    assert extract_candidates_from_pages([page]) == []



def test_aaa_detail_page_without_main_strips_site_header_from_fallback():
    html = """
    <html><body>
      <header class="site-header">
        <div>COUNSELLING CODE : 4680</div>
        <nav>
          <a href="/payments">ONLINE FEE PAYMENT</a>
          <a href="/login">STAFF LOGIN</a>
        </nav>
      </header>
      <div class="page-content">
        <h2>From Campus to Career: Transenergy Pvt. Ltd. Recruitment Drive on 10-10-2026</h2>
        <p>
          AAA College of Engineering and Technology successfully conducted a
          Campus Recruitment Drive by Transenergy Pvt. Ltd., Chennai, on
          10 October 2026 for final-year students.
        </p>
      </div>
    </body></html>
    """
    page = _page(
        "header navigation before the event content",
        url=(
            "https://aaaenggcoll.ac.in/"
            "from-campus-to-career-transenergy-pvt-ltd-recruitment-drive-on-10-10-2026"
        ),
        institution="AAA College of Engineering & Technology",
    )
    page["html"] = html

    candidates = extract_candidates_from_pages([page])

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.company_name == "Transenergy Pvt. Ltd."
    assert "ONLINE FEE PAYMENT" not in candidate.raw_text_excerpt
    assert "COUNSELLING CODE" not in candidate.raw_text_excerpt





def test_company_extraction_ignores_social_links_before_gotrust():
    html = """
    <html><body>
      <main>
        <div class="social-links">
          <a>LinkedIn</a><a>Instagram</a><a>Whatsapp</a><a>Youtube</a>
        </div>
        <h2>GoTrust Campus Recruitment Drive</h2>
        <p>GoTrust campus recruitment drive for graduating students.</p>
      </main>
    </body></html>
    """
    candidate = extract_event_candidate(
        html,
        "LinkedIn Instagram Whatsapp Youtube GoTrust Campus Recruitment Drive",
        "https://example.edu/notice/gotrust-campus-recruitment-drive",
        {"institution": "Test College", "seed_url": "https://example.edu/notice"},
    )

    assert candidate is not None
    assert candidate.company_name == "GoTrust"
    assert "\\n" not in candidate.company_name
    assert "LinkedIn" not in candidate.company_name


def test_company_extraction_handles_itc_sentence_without_capturing_tail_fragment():
    html = """
    <html><body><main>
      <article>
        <h1>ITC Limited campus recruitment MBA Marketing 2027</h1>
        <div class="entry-content">
          <p>ITC Limited</p>
          <p>will be conducting a Campus Recruitment Drive for MBA Marketing
          candidates of 2027 batch. Registration closes 9 October 2026.</p>
        </div>
      </article>
    </main></body></html>
    """
    candidate = extract_event_candidate(
        html,
        "ITC Limited will be conducting a Campus Recruitment Drive",
        "https://example.edu/placementnotice/itc-limited-campus-recruitment",
        {"institution": "Test College", "seed_url": "https://example.edu/placementnotice"},
    )

    assert candidate is not None
    assert candidate.company_name == "ITC Limited"
    assert "will be conducting" not in candidate.company_name.lower()
