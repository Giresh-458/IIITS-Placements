from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

from src.crawler.engine import CrawlerEngine
from src.orchestration.pipeline import PipelineOrchestrator
from src.orchestration.state import create_initial_state


def test_child_url_selection_is_deterministic_and_respects_remaining_budget():
    engine = CrawlerEngine(seeds=[])
    scheduled = {"https://example.edu/start"}
    selected = engine._select_child_urls(
        links=[
            ("/placementnotice/wp-login.php?action=logout", "Log out"),
            ("/about", "About"),
            ("/careers/a", "Open careers"),
            ("/notices/b", "Placement notices"),
            ("/careers/a", "Open careers again"),
            ("https://external.example/hiring", "Hiring"),
        ],
        page_url="https://example.edu/index",
        seed_url="https://example.edu/start",
        scheduled_urls=scheduled,
        remaining_slots=2,
    )

    assert selected == [
        "https://example.edu/careers/a",
        "https://example.edu/notices/b",
    ]
    assert len(scheduled) == 3
    assert all(urlparse(url).netloc == "example.edu" for url in selected)
    assert engine._select_child_urls(
        [("/careers/extra", "Careers")],
        "https://example.edu/index",
        "https://example.edu/start",
        scheduled,
        remaining_slots=0,
    ) == []


def _telemetry(*, successes, failed, source_stats):
    return SimpleNamespace(
        sources_attempted=successes + failed,
        sources_succeeded=successes,
        sources_failed=failed,
        pages_attempted=2,
        pages_failed=1 if failed else 0,
        http_requests=2,
        browser_pages=0,
        exceptions=[],
        source_stats=source_stats,
        model_dump=lambda mode="json": {
            "sources_attempted": successes + failed,
            "sources_succeeded": successes,
            "sources_failed": failed,
            "source_stats": source_stats,
        },
    )


@pytest.mark.asyncio
async def test_pipeline_crawling_propagates_measured_source_outcomes(monkeypatch):
    telemetry = _telemetry(
        successes=1,
        failed=1,
        source_stats={
            "College A": {
                "pages_visited": 1,
                "pages_succeeded": 1,
                "pages_failed": 0,
                "stop_reason": None,
            },
            "College B": {
                "pages_visited": 1,
                "pages_succeeded": 0,
                "pages_failed": 1,
                "stop_reason": "BLOCKED_OR_FORBIDDEN",
            },
        },
    )

    class FakeCrawlerEngine:
        def __init__(self, *args, **kwargs):
            pass

        async def run(self):
            return [], telemetry

    monkeypatch.setattr("src.crawler.engine.CrawlerEngine", FakeCrawlerEngine)
    state = create_initial_state(sources=[{}, {}])

    await PipelineOrchestrator()._do_crawling(state)

    assert state["telemetry"]["sources_succeeded"] == 1
    assert state["telemetry"]["sources_failed"] == 1
    assert state["failed_sources"] == [
        {
            "institution": "College B",
            "stop_reason": "BLOCKED_OR_FORBIDDEN",
            "pages_attempted": 1,
            "pages_succeeded": 0,
        }
    ]
    assert state["warnings"] == [
        "Crawling: 1 of 2 eligible sources had no successful page.",
        "Crawling: 1 page request(s) failed.",
    ]


@pytest.mark.asyncio
async def test_pipeline_crawling_fails_closed_when_every_source_fails(monkeypatch):
    telemetry = _telemetry(
        successes=0,
        failed=2,
        source_stats={
            "College A": {
                "pages_visited": 0,
                "pages_succeeded": 0,
                "pages_failed": 0,
                "stop_reason": "NO_SUCCESSFUL_PAGE",
            },
            "College B": {
                "pages_visited": 1,
                "pages_succeeded": 0,
                "pages_failed": 1,
                "stop_reason": "HTTP_503",
            },
        },
    )

    class FakeCrawlerEngine:
        def __init__(self, *args, **kwargs):
            pass

        async def run(self):
            return [], telemetry

    monkeypatch.setattr("src.crawler.engine.CrawlerEngine", FakeCrawlerEngine)
    state = create_initial_state(sources=[{}, {}])

    with pytest.raises(RuntimeError, match="Crawling failed for all 2 eligible sources"):
        await PipelineOrchestrator()._do_crawling(state)

    assert state["telemetry"]["sources_succeeded"] == 0
    assert state["telemetry"]["sources_failed"] == 2
    assert len(state["failed_sources"]) == 2
    assert state["warnings"] == [
        "Crawling: 2 of 2 eligible sources had no successful page.",
        "Crawling: 1 page request(s) failed.",
    ]



def test_record_page_success_updates_aggregate_and_per_source_counters():
    engine = CrawlerEngine(seeds=[])
    request = SimpleNamespace(
        id="request-1",
        unique_key="https://example.edu/placements",
        url="https://example.edu/placements",
    )

    engine._record_logical_page_attempt(request, "Example College")
    engine._record_http_request(request)
    engine._record_page_success(request, "Example College")
    # A retry of the same URL must not inflate logical URL counters.
    engine._record_page_success(request, "Example College")

    stats = engine.telemetry.source_stats["Example College"]
    assert engine.telemetry.pages_attempted == 1
    assert engine.telemetry.pages_succeeded == 1
    assert engine.telemetry.requests_attempted == 1
    assert engine.telemetry.requests_succeeded == 1
    assert engine.telemetry.http_requests == 1
    assert stats["pages_visited"] == 1
    assert stats["pages_succeeded"] == 1


@pytest.mark.asyncio
async def test_terminal_crawl_failure_callback_records_403_and_attempt_counts(monkeypatch):
    captured = {}

    class FakeCrawler:
        def __init__(self, **kwargs):
            self.request_handler = kwargs["request_handler"]
            self.error_callback = None
            self.failed_callback = None

        def error_handler(self, callback):
            self.error_callback = callback
            return callback

        def failed_request_handler(self, callback):
            self.failed_callback = callback
            return callback

        async def run(self, requests):
            from types import SimpleNamespace

            request = requests[0]
            captured["request"] = request

            def context_for(retry_count):
                # Simulate Crawlee's copied request context for each retry.
                attempt_request = SimpleNamespace(
                    url=request.url,
                    user_data=dict(request.user_data),
                    id=request.id,
                    unique_key=request.unique_key,
                    retry_count=retry_count,
                )
                return SimpleNamespace(request=attempt_request)

            error = RuntimeError(
                "Assuming the session is blocked based on HTTP status code 403"
            )
            await self.error_callback(context_for(0), error)
            await self.error_callback(context_for(1), error)
            await self.failed_callback(context_for(2), error)

    monkeypatch.setattr("src.crawler.engine.BeautifulSoupCrawler", FakeCrawler)
    engine = CrawlerEngine(seeds=[{
        "institution": "Example College",
        "seed_url": "https://example.edu/placements",
        "source_category": "P0_DIRECT_EVENT_FEED",
        "crawl_limits": {"max_pages": 3, "max_depth": 1},
    }])

    events, telemetry = await engine.run()

    stats = telemetry.source_stats["Example College"]
    assert events == []
    assert telemetry.sources_attempted == 1
    assert telemetry.sources_succeeded == 0
    assert telemetry.sources_failed == 1
    assert telemetry.pages_attempted == 1
    assert telemetry.pages_failed == 1
    assert telemetry.http_requests == 1
    assert telemetry.retries == 2
    assert stats["pages_visited"] == 1
    assert stats["pages_succeeded"] == 0
    assert stats["pages_failed"] == 1
    assert stats["stop_reason"] == "BLOCKED_OR_FORBIDDEN"
    assert len(telemetry.exceptions) == 1
