import json

from run_batch_8 import validate_serialized_output


def _write_pair(tmp_path, events, leads):
    events_path = tmp_path / "events.json"
    leads_path = tmp_path / "leads.json"
    events_path.write_text(json.dumps(events), encoding="utf-8")
    leads_path.write_text(json.dumps(leads), encoding="utf-8")
    return str(events_path), str(leads_path)


def _lead_for(event):
    classification = event.get("business_classification", {})
    return {
        "canonical_event_id": event.get("canonical_identity") or event.get("event_id"),
        "company_name": event.get("company_name"),
        "role": event.get("role"),
        "batch": event.get("batch"),
        "branches": event.get("eligible_branches", []),
        "ctc": event.get("ctc"),
        "event_date": event.get("event_date"),
        "registration_deadline": event.get("registration_deadline"),
        "role_relevance": classification.get("role_relevance"),
        "fresher_scope": classification.get("fresher_scope"),
        "branch_qualification": classification.get("branch_qualification"),
        "package_qualification": classification.get("package_qualification"),
        "target_fit": classification.get("target_fit"),
        "temporal_status": classification.get("temporal_status"),
    }


def test_filtered_out_events_are_intentionally_excluded_from_lead_output(tmp_path):
    filtered = {
        "event_id": "filtered-1",
        "canonical_identity": "filtered-1",
        "company_name": "Expired Corp",
        "business_classification": {"target_fit": "FILTERED_OUT"},
    }
    included = {
        "event_id": "included-1",
        "canonical_identity": "included-1",
        "company_name": "Active Corp",
        "role": "SDE",
        "batch": "2027",
        "eligible_branches": ["CSE", "IT"],
        "ctc": 10,
        "event_date": "2026-10-20",
        "registration_deadline": "2026-10-30",
        "business_classification": {
            "role_relevance": "CORE",
            "fresher_scope": "TRUE",
            "branch_qualification": "QUALIFIED",
            "package_qualification": "QUALIFIED",
            "target_fit": "QUALIFIED",
            "temporal_status": "ACTIVE_OPPORTUNITY",
        },
    }
    events_path, leads_path = _write_pair(
        tmp_path, [filtered, included], [_lead_for(included)]
    )

    valid, message = validate_serialized_output(events_path, leads_path)

    assert valid, message


def test_filtered_out_event_must_not_be_emitted_as_a_lead(tmp_path):
    filtered = {
        "event_id": "filtered-1",
        "canonical_identity": "filtered-1",
        "company_name": "Expired Corp",
        "business_classification": {"target_fit": "FILTERED_OUT"},
    }
    events_path, leads_path = _write_pair(
        tmp_path, [filtered], [_lead_for(filtered)]
    )

    valid, message = validate_serialized_output(events_path, leads_path)

    assert not valid
    assert "Canonical ID mismatch" in message


def test_missing_non_filtered_event_still_fails_validation(tmp_path):
    included = {
        "event_id": "included-1",
        "canonical_identity": "included-1",
        "company_name": "Active Corp",
        "business_classification": {"target_fit": "QUALIFIED"},
    }
    events_path, leads_path = _write_pair(tmp_path, [included], [])

    valid, message = validate_serialized_output(events_path, leads_path)

    assert not valid
    assert "Canonical ID mismatch" in message


def test_only_filtered_out_events_can_produce_empty_lead_list(tmp_path):
    events = [
        {
            "event_id": "filtered-1",
            "canonical_identity": "filtered-1",
            "business_classification": {"target_fit": "FILTERED_OUT"},
        },
        {
            "event_id": "filtered-2",
            "canonical_identity": "filtered-2",
            "business_classification": {"target_fit": "FILTERED_OUT"},
        },
    ]
    events_path, leads_path = _write_pair(tmp_path, events, [])

    valid, message = validate_serialized_output(events_path, leads_path)

    assert valid, message
