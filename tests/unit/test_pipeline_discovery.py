import json

import pytest

from src.orchestration.pipeline import PipelineOrchestrator
from src.orchestration.state import create_initial_state


def _source(category="P0_DIRECT_EVENT_FEED", institution="Example College", **extra):
    source = {
        "institution": institution,
        "seed_url": "https://example.edu/placements",
        "source_category": category,
        "crawl_limits": {"max_pages": 3, "max_depth": 1},
    }
    source.update(extra)
    return source


def _write_registry(root, payload):
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "crawl_seed_registry.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_discovery_uses_explicit_source_override_without_reading_registry(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    provided = _source(institution="Injected College")
    state = create_initial_state(sources=[provided])

    await PipelineOrchestrator()._do_discovery(state)

    assert state["sources"] == [provided]
    assert state["telemetry"]["sources_attempted"] == 1
    assert state["stop_reason"] is None


@pytest.mark.asyncio
async def test_discovery_preserves_explicit_empty_override_and_fails_closed(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    _write_registry(tmp_path, [_source()])
    state = create_initial_state(sources=[])

    with pytest.raises(RuntimeError, match="no crawlable sources"):
        await PipelineOrchestrator()._do_discovery(state)

    # The explicit empty override must not fall back to the file registry.
    assert state["sources"] == []


@pytest.mark.asyncio
async def test_discovery_selects_only_categories_supported_by_crawler(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    seeds = [
        _source("P0_DIRECT_EVENT_FEED", "Direct Feed"),
        _source("P0_PUBLIC_EVENT_ARCHIVE", "Public Archive"),
        _source("P0_EVENT_INDEX_WITH_CHILD_DETAILS", "Event Index"),
        _source("P1_PUBLIC_NOTICE_INDEX", "Notice Index"),
        _source("AUTHENTICATED_PORTAL", "Login Portal"),
    ]
    _write_registry(tmp_path, seeds)
    state = create_initial_state()

    await PipelineOrchestrator()._do_discovery(state)

    assert [s["institution"] for s in state["sources"]] == [
        "Direct Feed",
        "Public Archive",
        "Event Index",
    ]
    assert state["telemetry"]["sources_attempted"] == 3


@pytest.mark.asyncio
async def test_discovery_rejects_non_list_registry_and_sets_failed_stage(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    _write_registry(tmp_path, {"source": _source()})
    state = create_initial_state()

    await PipelineOrchestrator()._safe_execute(
        state, "DISCOVERY", PipelineOrchestrator()._do_discovery
    )

    assert state["terminal_status"] == "FAILED"
    assert state["errors"][0]["stage"] == "DISCOVERY"
    assert "must be a JSON list" in state["stop_reason"]


@pytest.mark.asyncio
async def test_discovery_rejects_malformed_selected_source(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    bad_source = _source()
    bad_source["seed_url"] = "file:///etc/passwd"
    _write_registry(tmp_path, [bad_source])
    state = create_initial_state()

    with pytest.raises(RuntimeError, match="invalid HTTP\(S\) seed_url"):
        await PipelineOrchestrator()._do_discovery(state)


@pytest.mark.asyncio
async def test_discovery_rejects_invalid_page_budget(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    bad_source = _source()
    bad_source["crawl_limits"]["max_pages"] = 0
    _write_registry(tmp_path, [bad_source])
    state = create_initial_state()

    with pytest.raises(RuntimeError, match="max_pages must be a positive integer"):
        await PipelineOrchestrator()._do_discovery(state)


@pytest.mark.asyncio
async def test_discovery_rejects_registry_with_no_crawlable_categories(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    _write_registry(
        tmp_path,
        [
            _source("P1_PUBLIC_NOTICE_INDEX"),
            _source("AUTHENTICATED_PORTAL"),
        ],
    )
    state = create_initial_state()

    with pytest.raises(RuntimeError, match="no crawlable sources"):
        await PipelineOrchestrator()._do_discovery(state)


@pytest.mark.asyncio
async def test_discovery_rejects_malformed_json_registry(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "crawl_seed_registry.json").write_text("{not-json", encoding="utf-8")
    state = create_initial_state()

    with pytest.raises(RuntimeError, match="Could not load discovery registry"):
        await PipelineOrchestrator()._do_discovery(state)
