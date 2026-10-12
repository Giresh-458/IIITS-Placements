import json
import subprocess
from pathlib import Path

import pytest

from src.orchestration.pipeline import PipelineOrchestrator


def _write_valid_batch8_outputs(root: Path):
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "outreach_leads.json").write_text("[]", encoding="utf-8")
    (artifacts / "outreach_contacts.json").write_text("[]", encoding="utf-8")
    (artifacts / "outreach_telemetry.json").write_text(
        json.dumps({"exceptions": 0, "stop_reason": "COMPLETED"}),
        encoding="utf-8",
    )
    (artifacts / "batch_8_reconciliation.md").write_text(
        "# Batch 8 Reconciliation\n", encoding="utf-8"
    )
    (artifacts / "batch_8_final_validation.md").write_text(
        "# Batch 8 Final Validation\n\nBATCH 8 = PASS\n", encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_consolidation_failure_cannot_reuse_previous_artifacts(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    output_names = [
        "outreach_leads.json",
        "outreach_contacts.json",
        "outreach_telemetry.json",
        "batch_8_reconciliation.md",
        "batch_8_final_validation.md",
    ]
    for name in output_names:
        (artifacts / name).write_text("stale", encoding="utf-8")

    def fake_run(args, **kwargs):
        assert args[-1] == "run_batch_8.py"
        assert all(not (artifacts / name).exists() for name in output_names)
        return subprocess.CompletedProcess(args, 1, "", "simulated Batch 8 failure")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="Batch 8 failed with exit code 1"):
        await PipelineOrchestrator()._do_consolidation({"telemetry": {}})

    assert all(not (artifacts / name).exists() for name in output_names)


@pytest.mark.asyncio
async def test_consolidation_rejects_success_without_required_outputs(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "artifacts").mkdir()

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, "done", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="did not produce required fresh artifacts"):
        await PipelineOrchestrator()._do_consolidation({"telemetry": {}})


@pytest.mark.asyncio
async def test_consolidation_rejects_hold_validation_report(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _write_valid_batch8_outputs(tmp_path)
    (tmp_path / "artifacts" / "batch_8_final_validation.md").write_text(
        "# Batch 8 Final Validation\n\nBATCH 8 = HOLD\n", encoding="utf-8"
    )

    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, "done", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="does not contain 'BATCH 8 = PASS'"):
        await PipelineOrchestrator()._do_consolidation({"telemetry": {}})


@pytest.mark.asyncio
async def test_consolidation_loads_fresh_validated_outputs(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def fake_run(args, **kwargs):
        _write_valid_batch8_outputs(tmp_path)
        return subprocess.CompletedProcess(args, 0, "done", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    state = {"telemetry": {}}

    result = await PipelineOrchestrator()._do_consolidation(state)

    assert result["consolidated_leads"] == []
    assert result["telemetry"]["consolidated_leads"] == 0
    assert result["telemetry"]["batch_8_telemetry"]["stop_reason"] == "COMPLETED"
