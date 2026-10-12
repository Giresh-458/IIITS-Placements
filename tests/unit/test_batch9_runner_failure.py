import json
from contextlib import asynccontextmanager

import pytest

import run_batch_9 as batch9_runner
from src.orchestration.ingestion import IngestionError


class _FakeResult:
    def scalars(self):
        return self

    def all(self):
        return []


class _FakeSession:
    async def scalar(self, statement):
        return 0

    async def execute(self, statement):
        return _FakeResult()


class _FakeDatabaseManager:
    def __init__(self):
        self.session = _FakeSession()

    async def connect(self):
        return None

    async def check_health(self):
        return True

    @asynccontextmanager
    async def session_maker(self):
        yield self.session

    async def disconnect(self):
        return None


@pytest.mark.asyncio
async def test_first_ingestion_failure_writes_failure_artifacts(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    leads_path = artifacts_dir / "outreach_leads.json"
    contacts_path = artifacts_dir / "outreach_contacts.json"
    leads_path.write_text(
        json.dumps([{"canonical_event_id": "event-1"}]),
        encoding="utf-8",
    )
    contacts_path.write_text("[]", encoding="utf-8")

    fake_db = _FakeDatabaseManager()
    monkeypatch.setattr(batch9_runner, "DatabaseManager", lambda: fake_db)

    class _FailingIngestion:
        def __init__(self, db_manager):
            pass

        async def ingest_snapshot(self, leads_path, contacts_path):
            raise IngestionError("deliberate test failure")

    monkeypatch.setattr(batch9_runner, "Batch9Ingestion", _FailingIngestion)

    await batch9_runner.run_batch_9(str(leads_path), str(contacts_path))

    telemetry_path = artifacts_dir / "batch_9_telemetry.json"
    reconciliation_path = artifacts_dir / "batch_9_reconciliation.md"
    validation_path = artifacts_dir / "batch_9_final_validation.md"

    assert telemetry_path.is_file()
    assert reconciliation_path.is_file()
    assert validation_path.is_file()

    telemetry = json.loads(telemetry_path.read_text(encoding="utf-8"))
    assert telemetry["exceptions"] == 1
    assert telemetry["stop_reason"] == "INGESTION_ERROR"
    assert telemetry["snapshots_processed"] == 0
    assert telemetry["run_1"]["status"] == "FAILED"
    assert telemetry["run_1"]["rejected"] == 1
    assert telemetry["run_2"]["status"] == "NOT_ATTEMPTED"
    assert telemetry["rejected"] == 1

    report = reconciliation_path.read_text(encoding="utf-8")
    assert "status = FAILED" in report
    assert "status = NOT_ATTEMPTED" in report

    validation = validation_path.read_text(encoding="utf-8")
    assert "Stop Reason: INGESTION_ERROR" in validation
    assert "BATCH 9 = HOLD" in validation
