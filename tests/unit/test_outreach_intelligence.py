import os
import json
import pytest

from run_batch_8 import run_batch_8

@pytest.fixture
def temp_artifacts(tmp_path):
    events_path = tmp_path / "classified_events.json"
    contacts_path = tmp_path / "normalized_contacts.json"
    evidence_path = tmp_path / "contact_evidence_audit.json"
    batch_7_val_path = tmp_path / "batch_7_final_validation.md"
    
    out_leads_path = tmp_path / "outreach_leads.json"
    out_contacts_path = tmp_path / "outreach_contacts.json"
    out_telemetry_path = tmp_path / "outreach_telemetry.json"
    out_recon_path = tmp_path / "batch_8_reconciliation.md"
    out_val_path = tmp_path / "batch_8_final_validation.md"
    
    def run_with_data(events, verified_contacts, test_status_override=None, write_md=True, evidence=None):
        events_path.write_text(json.dumps(events))
        contacts_path.write_text(json.dumps(verified_contacts))
        evidence_path.write_text(json.dumps(evidence or []))
        
        if write_md:
            companies = set([e.get("company_name") for e in events if e.get("company_name") and e.get("company_name").upper() not in ["UNKNOWN", "ANONYMOUS", "NONE", ""]])
            overrides = test_status_override or {}
            md = "| Company | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | Final Status |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
            for c in companies:
                status = overrides.get(c, "NO_VERIFIED_PHONE")
                md += f"| {c} | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | {status} |\n"
            batch_7_val_path.write_text(md)
        else:
            if batch_7_val_path.exists():
                batch_7_val_path.unlink()
        
        success = run_batch_8(
            events_path=str(events_path),
            contacts_path=str(contacts_path),
            evidence_path=str(evidence_path),
            batch_7_val_path=str(batch_7_val_path),
            out_leads_path=str(out_leads_path),
            out_contacts_path=str(out_contacts_path),
            out_telemetry_path=str(out_telemetry_path),
            out_recon_path=str(out_recon_path),
            out_val_path=str(out_val_path)
        )
        
        leads = json.loads(out_leads_path.read_text()) if out_leads_path.exists() else []
        contacts = json.loads(out_contacts_path.read_text()) if out_contacts_path.exists() else []
        telemetry = json.loads(out_telemetry_path.read_text()) if out_telemetry_path.exists() else {}
        
        return success, leads, contacts, telemetry
        
    return run_with_data

def test_hot_recent_event_correct_priority(temp_artifacts):
    events = [{
        "event_id": "1",
        "company_name": "Acme Corp",
        "business_classification": {
            "temporal_status": "HOT_OUTREACH_LEAD",
            "target_fit": "QUALIFIED",
            "role_relevance": "CORE"
        }
    }]
    _, leads, _, _ = temp_artifacts(events, [])
    assert len(leads) == 1
    assert leads[0]["outreach_priority"] == "P0"

def test_active_event_not_hot(temp_artifacts):
    events = [{
        "event_id": "1",
        "company_name": "Acme Corp",
        "business_classification": {
            "temporal_status": "ACTIVE_OPPORTUNITY",
            "target_fit": "QUALIFIED",
            "role_relevance": "CORE"
        }
    }]
    _, leads, _, _ = temp_artifacts(events, [])
    assert leads[0]["outreach_priority"] == "P1"

def test_filtered_out_not_high_priority(temp_artifacts):
    events = [{
        "event_id": "1",
        "company_name": "Acme Corp",
        "business_classification": {
            "temporal_status": "HOT_OUTREACH_LEAD",
            "target_fit": "FILTERED_OUT",
            "role_relevance": "CORE"
        }
    }]
    _, leads, _, _ = temp_artifacts(events, [])
    assert len(leads) == 0

def test_review_target_fit_partial_handling(temp_artifacts):
    events = [{
        "event_id": "1",
        "company_name": "Acme Corp",
        "business_classification": {
            "temporal_status": "HOT_OUTREACH_LEAD",
            "target_fit": "REVIEW",
            "role_relevance": "UNKNOWN"
        }
    }]
    _, leads, _, _ = temp_artifacts(events, [])
    assert leads[0]["outreach_priority"] == "P2"
    assert leads[0]["outreach_readiness"] == "REVIEW"

def test_missing_phone_event_preserved(temp_artifacts):
    events = [{
        "event_id": "1",
        "company_name": "Acme Corp",
        "business_classification": {
            "temporal_status": "HOT_OUTREACH_LEAD",
            "target_fit": "QUALIFIED",
            "role_relevance": "CORE"
        }
    }]
    _, leads, _, telemetry = temp_artifacts(events, [])
    assert len(leads) == 1
    assert leads[0]["contact_status"] == "NO_VERIFIED_PUBLIC_RECRUITMENT_PHONE"
    assert leads[0]["outreach_readiness"] == "PARTIAL"
    assert telemetry["no_phone_events"] == 1

def test_verified_contact_correctly_linked(temp_artifacts):
    events = [{
        "event_id": "1",
        "canonical_identity": "c_1",
        "company_name": "Acme Corp",
        "business_classification": {
            "temporal_status": "HOT_OUTREACH_LEAD",
            "target_fit": "QUALIFIED",
            "role_relevance": "CORE"
        }
    }]
    verified = [{
        "contact_id": "c1",
        "company_name": "Acme Corp",
        "phone_normalized": "1234567890",
        "contact_role": "RECRUITER",
        "verification_state": "VERIFIED"
    }]
    evidence = [{
        "contact_id": "c1",
        "evidence_text": "Found on careers page",
        "source_url": "acme.com/careers"
    }]
    _, leads, contacts, telemetry = temp_artifacts(events, verified, evidence=evidence)
    assert leads[0]["contact_status"] == "VERIFIED_RECRUITMENT_CONTACT"
    assert "c1" in leads[0]["verified_contact_ids"]
    assert leads[0]["outreach_readiness"] == "READY"
    assert len(contacts) == 1
    assert "c_1" in contacts[0]["linked_event_ids"]
    assert contacts[0]["evidence"]["evidence_text"] == "Found on careers page"

def test_incomplete_discovery_not_no_phone(temp_artifacts):
    events = [{
        "event_id": "1",
        "company_name": "Acme Corp",
        "business_classification": {
            "temporal_status": "HOT_OUTREACH_LEAD",
            "target_fit": "QUALIFIED",
            "role_relevance": "CORE"
        }
    }]
    test_override = {"Acme Corp": "INCOMPLETE"}
    _, leads, _, telemetry = temp_artifacts(events, [], test_status_override=test_override)
    assert leads[0]["contact_status"] == "CONTACT_DISCOVERY_INCOMPLETE"
    assert telemetry["incomplete_contact_discovery_events"] == 1
    assert telemetry["no_phone_events"] == 0

def test_company_identity_required_blocked(temp_artifacts):
    events = [{
        "event_id": "1",
        "company_name": "UNKNOWN",
        "business_classification": {
            "temporal_status": "HOT_OUTREACH_LEAD",
            "target_fit": "QUALIFIED",
            "role_relevance": "CORE"
        }
    }]
    _, leads, _, _ = temp_artifacts(events, [])
    assert leads[0]["contact_status"] == "COMPANY_IDENTITY_REQUIRED"
    assert leads[0]["outreach_readiness"] == "BLOCKED"
    assert leads[0]["outreach_priority"] == "P3"

def test_multiple_events_same_company_lineage_preserved(temp_artifacts):
    events = [
        {"event_id": "e1", "company_name": "Acme Corp", "business_classification": {}},
        {"event_id": "e2", "company_name": "Acme Corp", "business_classification": {}}
    ]
    verified = [{
        "contact_id": "c1", "company_name": "Acme Corp", "phone_normalized": "123", "verification_state": "VERIFIED", "contact_role": "RECRUITER"
    }]
    _, leads, contacts, telemetry = temp_artifacts(events, verified)
    assert len(leads) == 2
    assert leads[0]["canonical_event_id"] == "e1"
    assert leads[1]["canonical_event_id"] == "e2"
    assert len(contacts) == 1
    assert "e1" in contacts[0]["linked_event_ids"]
    assert "e2" in contacts[0]["linked_event_ids"]

def test_same_company_different_events_not_merged(temp_artifacts):
    events = [
        {"event_id": "e1", "company_name": "Acme Corp", "role": "Developer", "business_classification": {}},
        {"event_id": "e2", "company_name": "Acme Corp", "role": "Tester", "business_classification": {}}
    ]
    _, leads, _, _ = temp_artifacts(events, [])
    assert len(leads) == 2
    assert leads[0]["role"] == "Developer"
    assert leads[1]["role"] == "Tester"

def test_all_input_event_counts_reconcile(temp_artifacts):
    events = [
        {"event_id": f"e{i}", "company_name": "Acme Corp", "business_classification": {}} for i in range(11)
    ]
    success, leads, _, telemetry = temp_artifacts(events, [])
    assert success
    assert len(leads) == 11
    assert telemetry["events_processed"] == 11
    assert telemetry["events_emitted"] == 11

def test_no_fabricated_facts(temp_artifacts):
    events = [{
        "event_id": "1",
        "company_name": "Acme Corp",
        "role": "SDE",
        "ctc": "10LPA",
        "business_classification": {
            "temporal_status": "UNKNOWN",
            "target_fit": "UNKNOWN",
            "role_relevance": "UNKNOWN"
        }
    }]
    _, leads, _, _ = temp_artifacts(events, [])
    lead = leads[0]
    assert lead["role"] == "SDE"
    assert lead["ctc"] == "10LPA"
    assert lead["temporal_status"] == "UNKNOWN"
    assert lead["target_fit"] == "UNKNOWN"
    
def test_boundary_hot_review(temp_artifacts):
    events = [{"event_id": "1", "company_name": "C", "business_classification": {"temporal_status": "HOT_OUTREACH_LEAD", "target_fit": "REVIEW", "role_relevance": "CORE"}}]
    _, leads, _, _ = temp_artifacts(events, [])
    assert leads[0]["outreach_priority"] == "P2"
    assert leads[0]["outreach_readiness"] == "REVIEW"

def test_boundary_hot_filtered(temp_artifacts):
    events = [{"event_id": "1", "company_name": "C", "business_classification": {"temporal_status": "HOT_OUTREACH_LEAD", "target_fit": "FILTERED_OUT", "role_relevance": "CORE"}}]
    _, leads, _, _ = temp_artifacts(events, [])
    assert len(leads) == 0

def test_boundary_active_qualified(temp_artifacts):
    events = [{"event_id": "1", "company_name": "C", "business_classification": {"temporal_status": "ACTIVE_OPPORTUNITY", "target_fit": "QUALIFIED", "role_relevance": "CORE"}}]
    _, leads, _, _ = temp_artifacts(events, [])
    assert leads[0]["outreach_priority"] == "P1"

def test_boundary_active_review(temp_artifacts):
    events = [{"event_id": "1", "company_name": "C", "business_classification": {"temporal_status": "ACTIVE_OPPORTUNITY", "target_fit": "REVIEW", "role_relevance": "CORE"}}]
    _, leads, _, _ = temp_artifacts(events, [])
    assert leads[0]["outreach_priority"] == "P2"

def test_boundary_unknown_review(temp_artifacts):
    events = [{"event_id": "1", "company_name": "C", "business_classification": {"temporal_status": "UNKNOWN", "target_fit": "REVIEW", "role_relevance": "CORE"}}]
    _, leads, _, _ = temp_artifacts(events, [])
    assert leads[0]["outreach_priority"] == "P3"

def test_invalid_contact_excluded(temp_artifacts):
    events = [{"event_id": "1", "company_name": "C", "business_classification": {}}]
    verified = [{
        "contact_id": "c1", "company_name": "C", "phone_normalized": "123", "verification_state": "REJECTED", "contact_role": "RECRUITER"
    }]
    _, leads, contacts, _ = temp_artifacts(events, verified)
    assert len(contacts) == 0
    assert leads[0]["contact_status"] == "NO_VERIFIED_PUBLIC_RECRUITMENT_PHONE"

def test_missing_batch_7_outcome(temp_artifacts):
    events = [{"event_id": "1", "company_name": "Acme Corp", "business_classification": {}}]
    success, leads, _, telemetry = temp_artifacts(events, [], write_md=False)
    assert not success
    assert leads[0]["contact_status"] == "BATCH_7_OUTCOME_MISSING"
    assert telemetry["missing_batch_7_outcome_events"] == 1
    assert telemetry["exceptions"] == 1
    
def test_company_missing_from_batch_7_table(temp_artifacts, tmp_path):
    events = [
        {"event_id": "1", "company_name": "Acme Corp", "business_classification": {}},
        {"event_id": "2", "company_name": "Other Corp", "business_classification": {}}
    ]
    events_path = tmp_path / "c_events.json"
    contacts_path = tmp_path / "n_contacts.json"
    evidence_path = tmp_path / "evidence.json"
    batch_7_val_path = tmp_path / "b7_val.md"
    
    events_path.write_text(json.dumps(events))
    contacts_path.write_text("[]")
    evidence_path.write_text("[]")
    
    md = "| Company | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | Final Status |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    md += f"| Acme Corp | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | NO_VERIFIED_PHONE |\n"
    batch_7_val_path.write_text(md)
    
    out_leads_path = tmp_path / "ol.json"
    out_contacts_path = tmp_path / "oc.json"
    out_telemetry_path = tmp_path / "ot.json"
    out_recon_path = tmp_path / "or.md"
    out_val_path = tmp_path / "ov.md"
    
    success = run_batch_8(
        events_path=str(events_path),
        contacts_path=str(contacts_path),
        evidence_path=str(evidence_path),
        batch_7_val_path=str(batch_7_val_path),
        out_leads_path=str(out_leads_path),
        out_contacts_path=str(out_contacts_path),
        out_telemetry_path=str(out_telemetry_path),
        out_recon_path=str(out_recon_path),
        out_val_path=str(out_val_path)
    )
    assert not success
    leads = json.loads(out_leads_path.read_text())
    tel = json.loads(out_telemetry_path.read_text())
    assert leads[1]["company_name"] == "Other Corp"
    assert leads[1]["contact_status"] == "BATCH_7_OUTCOME_MISSING"
    assert tel["missing_batch_7_outcome_events"] == 1

def test_malformed_batch_7_table(temp_artifacts, tmp_path):
    events = [{"event_id": "1", "company_name": "Acme Corp", "business_classification": {}}]
    events_path = tmp_path / "c_events.json"
    contacts_path = tmp_path / "n_contacts.json"
    evidence_path = tmp_path / "evidence.json"
    batch_7_val_path = tmp_path / "b7_val.md"
    
    events_path.write_text(json.dumps(events))
    contacts_path.write_text("[]")
    evidence_path.write_text("[]")
    
    md = "| Company | Final Status |\n|---|---|\n| Acme Corp | \n"
    batch_7_val_path.write_text(md)
    
    out_leads_path = tmp_path / "ol.json"
    out_contacts_path = tmp_path / "oc.json"
    out_telemetry_path = tmp_path / "ot.json"
    out_recon_path = tmp_path / "or.md"
    out_val_path = tmp_path / "ov.md"
    
    success = run_batch_8(
        events_path=str(events_path),
        contacts_path=str(contacts_path),
        evidence_path=str(evidence_path),
        batch_7_val_path=str(batch_7_val_path),
        out_leads_path=str(out_leads_path),
        out_contacts_path=str(out_contacts_path),
        out_telemetry_path=str(out_telemetry_path),
        out_recon_path=str(out_recon_path),
        out_val_path=str(out_val_path)
    )
    assert not success
    leads = json.loads(out_leads_path.read_text())
    assert leads[0]["contact_status"] == "BATCH_7_OUTCOME_MISSING"

def test_invalid_batch_7_outcome(temp_artifacts, tmp_path):
    events = [{"event_id": "1", "company_name": "Acme Corp", "business_classification": {}}]
    events_path = tmp_path / "c_events.json"
    contacts_path = tmp_path / "n_contacts.json"
    evidence_path = tmp_path / "evidence.json"
    batch_7_val_path = tmp_path / "b7_val.md"
    
    events_path.write_text(json.dumps(events))
    contacts_path.write_text("[]")
    evidence_path.write_text("[]")
    
    md = "| Company | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | Final Status |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    md += f"| Acme Corp | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | SOME_WEIRD_STATUS |\n"
    batch_7_val_path.write_text(md)
    
    out_leads_path = tmp_path / "ol.json"
    out_contacts_path = tmp_path / "oc.json"
    out_telemetry_path = tmp_path / "ot.json"
    out_recon_path = tmp_path / "or.md"
    out_val_path = tmp_path / "ov.md"
    
    success = run_batch_8(
        events_path=str(events_path),
        contacts_path=str(contacts_path),
        evidence_path=str(evidence_path),
        batch_7_val_path=str(batch_7_val_path),
        out_leads_path=str(out_leads_path),
        out_contacts_path=str(out_contacts_path),
        out_telemetry_path=str(out_telemetry_path),
        out_recon_path=str(out_recon_path),
        out_val_path=str(out_val_path)
    )
    # The invalid outcome sets contact_status to BATCH_7_OUTCOME_INVALID. 
    # That still allows a PASS if we are correctly tracking it, but wait!
    # "unknown/malformed status MUST NEVER become a definitive no-phone result"
    # Actually, does this fail the Batch 8 gate? 
    # The user says "missing/invalid statuses fail closed". Let me make sure is_pass = False if invalid > 0.
    assert not success
    leads = json.loads(out_leads_path.read_text())
    assert leads[0]["contact_status"] == "BATCH_7_OUTCOME_INVALID"

def test_completed_batch_7_outcome(temp_artifacts):
    events = [{"event_id": "1", "company_name": "Acme Corp", "business_classification": {}}]
    test_override = {"Acme Corp": "COMPLETED"}
    success, leads, _, telemetry = temp_artifacts(events, [], test_status_override=test_override)
    assert success
    assert leads[0]["contact_status"] == "NO_VERIFIED_PUBLIC_RECRUITMENT_PHONE"
    assert telemetry["no_phone_events"] == 1

from run_batch_8 import validate_serialized_output

def test_validator_branches_mismatch(tmp_path):
    events_path = tmp_path / "events.json"
    leads_path = tmp_path / "leads.json"
    
    events = [{
        "canonical_identity": "c1",
        "company_name": "C",
        "eligible_branches": ["CSE", "ECE"]
    }]
    leads = [{
        "canonical_event_id": "c1",
        "company_name": "C",
        "branches": ["CSE"]  # Missing ECE
    }]
    
    events_path.write_text(json.dumps(events))
    leads_path.write_text(json.dumps(leads))
    
    valid, msg = validate_serialized_output(str(events_path), str(leads_path))
    assert not valid
    assert "eligible_branches mismatch" in msg

def test_validator_branches_match(tmp_path):
    events_path = tmp_path / "events.json"
    leads_path = tmp_path / "leads.json"
    
    events = [{
        "canonical_identity": "c1",
        "company_name": "C",
        "eligible_branches": ["CSE", "ECE"]
    }]
    leads = [{
        "canonical_event_id": "c1",
        "company_name": "C",
        "branches": ["CSE", "ECE"]
    }]
    
    events_path.write_text(json.dumps(events))
    leads_path.write_text(json.dumps(leads))
    
    valid, msg = validate_serialized_output(str(events_path), str(leads_path))
    assert valid
