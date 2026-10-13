import json
from pathlib import Path

import pytest

from src.orchestration.pipeline import PipelineOrchestrator
from src.orchestration.state import create_initial_state


def _event(event_id="event-1", evidence=None):
    return {
        "event_id": event_id,
        "source_event_id": f"source-{event_id}",
        "canonical_identity": f"Trident|Berger Paints|2026-10-16|{event_id}",
        "institution": "Trident Academy of Technology",
        "company_name": "Berger Paints",
        "event_date": "2026-10-16",
        "event_url": "https://college.example/placementnotice/berger-drive",
        "source_seed_url": "https://college.example/placementnotice/",
        "raw_event_text": "Unrelated student phone: 9876543210",
        "evidence": evidence or [],
    }


@pytest.mark.asyncio
async def test_evidence_stage_builds_field_level_registry_and_artifact(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    state = create_initial_state()
    state["normalized_events"] = [
        _event(
            evidence=[
                {
                    "field": "company",
                    "raw_value": "Berger Paints",
                    "evidence_url": "https://college.example/placementnotice/berger-drive",
                    "evidence_text": "Berger Paints - GD Schedule",
                    "extraction_method": "structural_regex",
                    "confidence": 0.98,
                }
            ]
        )
    ]
    state["evidence"] = [{"stale": True}]

    result = await PipelineOrchestrator()._do_evidence(state)

    assert len(result["evidence"]) == 1
    item = result["evidence"][0]
    assert item["event_id"] == "event-1"
    assert item["source_event_id"] == "source-event-1"
    assert item["institution"] == "Trident Academy of Technology"
    assert item["company_name"] == "Berger Paints"
    assert item["field"] == "company"
    assert item["raw_value"] == "Berger Paints"
    assert item["evidence_url"] == "https://college.example/placementnotice/berger-drive"
    assert item["evidence_text"] == "Berger Paints - GD Schedule"
    assert item["extraction_method"] == "structural_regex"
    assert item["confidence"] == 0.98
    assert item["evidence_id"]
    assert "raw_event_text" not in item
    assert "9876543210" not in json.dumps(result["evidence"])

    artifact = Path("artifacts/event_evidence.json")
    assert artifact.is_file()
    assert json.loads(artifact.read_text(encoding="utf-8")) == result["evidence"]
    assert result["telemetry"]["evidence_records"] == 1
    assert result["telemetry"]["evidence_events_without_records"] == 0
    assert not any(w.startswith("Stage 6 Evidence:") for w in result["warnings"])


@pytest.mark.asyncio
async def test_evidence_stage_deduplicates_exact_records_but_keeps_distinct_evidence(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    evidence_item = {
        "field": "company",
        "raw_value": "Berger Paints",
        "evidence_text": "Berger Paints - GD Schedule",
        "extraction_method": "structural_regex",
    }
    state = create_initial_state()
    state["normalized_events"] = [
        _event(evidence=[evidence_item, dict(evidence_item), {
            "field": "event_date",
            "raw_value": "16th October 2026",
            "evidence_text": "on 16th October 2026",
            "extraction_method": "date_regex",
        }])
    ]

    orchestrator = PipelineOrchestrator()
    first = await orchestrator._do_evidence(state)
    first_records = list(first["evidence"])
    first_ids = [item["evidence_id"] for item in first_records]

    second = await orchestrator._do_evidence(state)

    assert len(first_records) == 2
    assert len(set(first_ids)) == 2
    assert second["evidence"] == first_records
    assert [item["evidence_id"] for item in second["evidence"]] == first_ids
    assert second["telemetry"]["evidence_records"] == 2


@pytest.mark.asyncio
async def test_evidence_stage_warns_for_events_without_field_evidence(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    state = create_initial_state()
    state["normalized_events"] = [
        _event(evidence=[{
            "field": "company",
            "raw_value": "Berger Paints",
            "evidence_text": "Berger Paints - GD Schedule",
        }]),
        _event(event_id="event-2", evidence=[]),
    ]

    result = await PipelineOrchestrator()._do_evidence(state)

    assert len(result["evidence"]) == 1
    assert result["telemetry"]["evidence_records"] == 1
    assert result["telemetry"]["evidence_events_without_records"] == 1
    stage_warnings = [
        w for w in result["warnings"] if w.startswith("Stage 6 Evidence:")
    ]
    assert stage_warnings == [
        "Stage 6 Evidence: event event-2 has no field-level evidence."
    ]
    assert json.loads(Path("artifacts/event_evidence.json").read_text()) == result["evidence"]


@pytest.mark.asyncio
async def test_evidence_stage_fails_closed_on_malformed_evidence_shape(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    state = create_initial_state()
    event = _event()
    event["evidence"] = {"company": "not-a-list"}
    state["normalized_events"] = [event]

    with pytest.raises(RuntimeError, match="must be a list"):
        await PipelineOrchestrator()._do_evidence(state)

    assert state["evidence"] == []
    assert not Path("artifacts/event_evidence.json").exists()
