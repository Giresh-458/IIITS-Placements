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
        hrefs=[
            "/careers/a",
            "/notices/b",
            "/careers/a",
            "https://external.example/hiring",
            "/about",
        ],
        page_url="https://example.edu/index",
        page_text="Latest college updates",
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
        ["/careers/extra"],
        "https://example.edu/index",
        "Latest college updates",
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
        "Crawling: 1 of 2 eligible sources had no successful page."
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
