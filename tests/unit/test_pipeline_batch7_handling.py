import ast
import json
import subprocess
from pathlib import Path

import pytest

from src.orchestration.pipeline import PipelineOrchestrator


def test_batch_7_script_has_valid_python_syntax():
    repository_root = Path(__file__).resolve().parents[2]
    script_path = repository_root / "run_batch_7.py"

    ast.parse(script_path.read_text(encoding="utf-8"), filename=str(script_path))


@pytest.mark.asyncio
async def test_contact_stage_stops_on_batch7_failure_and_removes_stale_output(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    contacts_path = tmp_path / "artifacts" / "normalized_contacts.json"
    contacts_path.parent.mkdir()
    contacts_path.write_text('[{"company_name": "stale"}]', encoding="utf-8")

    def fake_run(args, **kwargs):
        assert args[-1] == "run_batch_7.py"
        assert not contacts_path.exists(), "Previous-run output must be removed first"
        return subprocess.CompletedProcess(args, 1, "", "SyntaxError: simulated failure")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="Batch 7 failed with exit code 1"):
        await PipelineOrchestrator()._do_contact_intelligence({})

    assert not contacts_path.exists()


@pytest.mark.asyncio
async def test_contact_stage_rejects_success_without_fresh_output(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "artifacts").mkdir()

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, "completed", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="did not produce"):
        await PipelineOrchestrator()._do_contact_intelligence({})


@pytest.mark.asyncio
async def test_contact_stage_reads_fresh_output_after_success(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    contacts_path = tmp_path / "artifacts" / "normalized_contacts.json"
    contacts_path.parent.mkdir()
    contacts_path.write_text('[{"company_name": "stale"}]', encoding="utf-8")

    fresh_contacts = [{"company_name": "Example Technologies"}]

    def fake_run(args, **kwargs):
        contacts_path.write_text(json.dumps(fresh_contacts), encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "completed", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    state = await PipelineOrchestrator()._do_contact_intelligence({})

    assert state["contacts"] == fresh_contacts
