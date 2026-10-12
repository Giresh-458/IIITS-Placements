import json
from types import SimpleNamespace

import pytest

import run_final_tests
import run_validation
from scripts import run_pipeline
from src.config.settings import settings
from src.models.domain import HiringEventCandidate
from src.telemetry.crawl_metrics import CrawlTelemetry


def _write_crawl_artifacts(artifact_dir):
    artifact_dir.mkdir(parents=True, exist_ok=True)
    registry = [
        {
            "institution": "Example College",
            "seed_url": "https://example.edu/placements",
            "source_category": "P0_DIRECT_EVENT_FEED",
        }
    ]
    event = HiringEventCandidate(
        institution="Example College",
        source_seed_url="https://example.edu/placements",
        event_url="https://example.edu/placements/drive",
        is_recent=True,
    ).model_dump(mode="json")
    telemetry = CrawlTelemetry(
        run_id="test-run",
        sources_attempted=1,
        sources_succeeded=1,
        pages_attempted=2,
        pages_succeeded=2,
        http_requests=2,
        browser_pages=1,
        browser_escalations=1,
        browser_failures=0,
        stop_reason="QUEUE_EXHAUSTED",
        source_stats={
            "Example College": {
                "pages_visited": 2,
                "events_found": 1,
                "browser_escalations": 1,
                "stop_reason": "QUEUE_EXHAUSTED",
            }
        },
    ).model_dump(mode="json")

    files = {
        "crawl_seed_registry.json": registry,
        "discovered_events.json": [event],
        "crawl_telemetry.json": telemetry,
    }
    for name, payload in files.items():
        (artifact_dir / name).write_text(json.dumps(payload), encoding="utf-8")


def test_final_test_runner_propagates_pytest_exit_code(monkeypatch):
    captured = {}

    def fake_run(command, check):
        captured["command"] = command
        captured["check"] = check
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(run_final_tests.subprocess, "run", fake_run)

    assert run_final_tests.run_tests() == 7
    assert captured["command"] == [run_final_tests.sys.executable, "-m", "pytest"]
    assert captured["check"] is False
    assert "run_batch_9.py" not in captured["command"]


def test_validation_reports_observed_artifact_metrics(monkeypatch, tmp_path, capsys):
    artifact_dir = tmp_path / "artifacts"
    _write_crawl_artifacts(artifact_dir)
    monkeypatch.setattr(run_validation, "ARTIFACT_DIR", artifact_dir)

    assert run_validation.run_validation() == 0
    output = capsys.readouterr().out

    assert "ARTIFACT_SCHEMA_VALIDATION = PASS" in output
    assert "source_registry_records = 1" in output
    assert "discovered_event_records = 1" in output
    assert "browser_pages = 1" in output
    assert "crawl_stop_reason_recorded = QUEUE_EXHAUSTED" in output
    assert "process_exited_normally" not in output
    assert "JS-rendered event fixture" not in output


def test_validation_fails_when_required_artifacts_are_missing(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(run_validation, "ARTIFACT_DIR", tmp_path / "missing-artifacts")

    assert run_validation.run_validation() == 1
    output = capsys.readouterr().out

    assert "ARTIFACT_VALIDATION = FAIL" in output
    assert "crawl_seed_registry.json" in output
    assert "discovered_events.json" in output
    assert "crawl_telemetry.json" in output


def test_validation_rejects_malformed_discovered_events(
    monkeypatch, tmp_path, capsys
):
    artifact_dir = tmp_path / "artifacts"
    _write_crawl_artifacts(artifact_dir)
    (artifact_dir / "discovered_events.json").write_text("[42]", encoding="utf-8")
    monkeypatch.setattr(run_validation, "ARTIFACT_DIR", artifact_dir)

    assert run_validation.run_validation() == 1
    output = capsys.readouterr().out

    assert "ARTIFACT_VALIDATION = FAIL" in output
    assert "record 0 failed schema validation" in output


def test_validate_config_rejects_invalid_crawl_budget(monkeypatch, capsys):
    budget = SimpleNamespace(
        max_runtime_seconds=0,
        max_urls=100,
        max_pages_per_source=10,
        request_timeout_seconds=10,
        browser_timeout_seconds=10,
        max_depth=1,
        max_browser_pages=1,
        max_pdf_pages=2,
        max_retries=1,
        per_domain_delay_seconds=0,
    )
    eligibility = SimpleNamespace(
        recent_event_days_window=15,
        cse_min_lpa=10.0,
        ece_min_lpa=6.5,
    )
    monkeypatch.setattr(settings, "crawl_budget", budget)
    monkeypatch.setattr(settings, "eligibility", eligibility)

    assert run_pipeline.validate_config() == 1
    output = capsys.readouterr().out

    assert "CONFIG_VALIDATION = FAIL" in output
    assert "max_runtime_seconds must be greater than zero" in output


@pytest.mark.asyncio
async def test_health_command_reports_database_failure(monkeypatch, capsys):
    class FakeDatabaseManager:
        async def connect(self):
            return None

        async def check_health(self):
            return False

        async def disconnect(self):
            return None

    monkeypatch.setattr(run_pipeline, "DatabaseManager", FakeDatabaseManager)

    assert await run_pipeline.check_database_health() == 1
    output = capsys.readouterr().out

    assert "DATABASE_CONNECTIVITY = FAIL" in output
    assert "Pipeline health check: OK" not in output
