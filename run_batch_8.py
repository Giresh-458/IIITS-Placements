import json
import logging
import sys
import re
from datetime import datetime
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def parse_batch_7_validation(filepath):
    company_status = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        in_table = False
        for line in lines:
            if line.strip().startswith('| Company |') and 'Final Status' in line:
                in_table = True
                continue
            if in_table and line.strip().startswith('|---'):
                continue
            if in_table and line.strip().startswith('|'):
                parts = [p.strip() for p in line.split('|')]
                if len(parts) > 13:
                    company = parts[1]
                    status = parts[13]
                    if not company or not status:
                        raise ValueError(f"Malformed row in Batch 7 table: {line}")
                    if company in company_status:
                        raise ValueError(f"Duplicate company row in Batch 7 table: {company}")
                    company_status[company] = status
                else:
                    raise ValueError(f"Malformed row in Batch 7 table: {line}")
            elif in_table and not line.strip():
                in_table = False
    except Exception as e:
        logging.error(f"Error parsing Batch 7 validation: {e}")
        raise
    return company_status

def validate_serialized_output(events_path, leads_path):
    with open(events_path, "r", encoding="utf-8") as f:
        events = json.load(f)
    with open(leads_path, "r", encoding="utf-8") as f:
        leads = json.load(f)
        
    events_by_id = {e.get("canonical_identity") or e.get("event_id"): e for e in events}
    leads_by_id = {l.get("canonical_event_id"): l for l in leads}
    
    if len(events_by_id) != len(events) or len(leads_by_id) != len(leads):
        return False, "Duplicate canonical IDs found"

    # FILTERED_OUT is an intentional exclusion from the outreach-lead artifact.
    # Validate exact coverage against only events that should be emitted.
    expected_events_by_id = {
        cid: event
        for cid, event in events_by_id.items()
        if event.get("business_classification", {}).get("target_fit") != "FILTERED_OUT"
    }
        
    if set(expected_events_by_id.keys()) != set(leads_by_id.keys()):
        return False, "Canonical ID mismatch between expected output and serialized leads"
        
    for cid, event in expected_events_by_id.items():
        lead = leads_by_id[cid]
        bc = event.get("business_classification", {})
        
        for key in ["company_name", "role", "batch", "ctc", "event_date", "registration_deadline"]:
            if lead.get(key) != event.get(key):
                return False, f"Batch 6 fact {key} mismatch for {cid}"
        for key in ["role_relevance", "fresher_scope", "branch_qualification", "package_qualification", "target_fit", "temporal_status"]:
            if lead.get(key) != bc.get(key):
                return False, f"Batch 6 fact {key} mismatch for {cid}"
                
        if lead.get("branches") != event.get("eligible_branches", []):
            return False, f"Batch 6 fact eligible_branches mismatch for {cid}"
                
    return True, "Exact field-value preservation after serialization."

def run_batch_8(
    events_path="artifacts/classified_events.json",
    contacts_path="artifacts/normalized_contacts.json",
    evidence_path="artifacts/contact_evidence_audit.json",
    batch_7_val_path="artifacts/batch_7_final_validation.md",
    out_leads_path="artifacts/outreach_leads.json",
    out_contacts_path="artifacts/outreach_contacts.json",
    out_telemetry_path="artifacts/outreach_telemetry.json",
    out_recon_path="artifacts/batch_8_reconciliation.md",
    out_val_path="artifacts/batch_8_final_validation.md"
):
    logging.info("Starting Batch 8: Outreach Intelligence & Actionable Lead Consolidation")
    
    try:
        with open(events_path, "r", encoding="utf-8") as f:
            classified_events = json.load(f)
    except Exception as e:
        logging.error(f"Failed to load {events_path}: {e}")
        return False
        
    try:
        with open(contacts_path, "r", encoding="utf-8") as f:
            normalized_contacts = json.load(f)
    except FileNotFoundError:
        normalized_contacts = []
        
    try:
        with open(evidence_path, "r", encoding="utf-8") as f:
            evidence_audit = json.load(f)
    except FileNotFoundError:
        evidence_audit = []
        
    evidence_by_contact = {e.get("contact_id"): e for e in evidence_audit if e.get("contact_id")}
        
    # Authoritative Batch 7 outcomes loaded strictly from Batch 7 output.
    company_discovery_status = {}
    parser_error = None
    try:
        company_discovery_status = parse_batch_7_validation(batch_7_val_path)
    except Exception as e:
        parser_error = str(e)
        
    # Determine expected companies
    expected_named_companies = set()
    for event in classified_events:
        company = event.get("company_name")
        if company and company.upper() not in ["UNKNOWN", "ANONYMOUS", "NONE", ""]:
            expected_named_companies.add(company)
            
    # Check coverage
    coverage_error = None
    if parser_error:
        coverage_error = f"Batch 7 parsing failed: {parser_error}"
    elif expected_named_companies != set(company_discovery_status.keys()):
        coverage_error = f"Company coverage mismatch. Expected: {expected_named_companies}, Found: {set(company_discovery_status.keys())}"
        
    outreach_leads = []
    outreach_contacts = []
    
    company_to_verified = defaultdict(list)
    for vc in normalized_contacts:
        if not vc.get("contact_id") or not vc.get("company_name"):
            continue
        phone = vc.get("phone_normalized") or vc.get("phone_raw")
        if not phone:
            continue
        if vc.get("verification_state") != "VERIFIED":
            continue
        role = vc.get("contact_role")
        if role in ["UNKNOWN", "SALES", "CUSTOMER_SUPPORT", "COMPANY_SWITCHBOARD", None]:
            continue
            
        evidence_record = evidence_by_contact.get(vc.get("contact_id"), {})
        evidence_text = evidence_record.get("evidence_text") or vc.get("evidence_text") or ""
        source_url = evidence_record.get("source_url") or vc.get("source_url") or ""
            
        company_to_verified[vc["company_name"]].append(vc)
        outreach_contacts.append({
            "contact_id": vc.get("contact_id"),
            "company": vc.get("company_name"),
            "person_name": vc.get("person_name"),
            "contact_role": vc.get("contact_role"),
            "phone": phone,
            "verification_state": vc.get("verification_state"),
            "confidence": vc.get("phone_confidence", "UNKNOWN"),
            "linked_event_ids": [], 
            "evidence": {
                "evidence_text": evidence_text,
                "source_url": source_url
            }
        })

    telemetry = {
        "events_processed": len(classified_events),
        "events_emitted": 0,
        "events_by_temporal_status": defaultdict(int),
        "events_by_target_fit": defaultdict(int),
        "events_by_priority": defaultdict(int),
        "events_by_readiness": defaultdict(int),
        "verified_contacts_linked": 0,
        "no_phone_events": 0,
        "incomplete_contact_discovery_events": 0,
        "identity_required_events": 0,
        "missing_batch_7_outcome_events": 0,
        "invalid_batch_7_outcome_events": 0,
        "filtered_out_events": 0,
        "exceptions": 1 if coverage_error else 0,
        "stop_reason": "COMPLETED" if not coverage_error else "COVERAGE_ERROR"
    }

    for event in classified_events:
        try:
            bc = event.get("business_classification", {})
            temporal_status = bc.get("temporal_status", "UNKNOWN")
            target_fit = bc.get("target_fit", "UNKNOWN")
            role_relevance = bc.get("role_relevance", "UNKNOWN")
            
            telemetry["events_by_temporal_status"][temporal_status] += 1
            telemetry["events_by_target_fit"][target_fit] += 1
            
            company = event.get("company_name")
            is_unknown_company = not company or company.upper() in ["UNKNOWN", "ANONYMOUS", "NONE", ""]
            
            # Contact Status mapped authoritatively from Batch 7 metrics.
            contact_status = "BATCH_7_OUTCOME_MISSING"
            linked_contact_ids = []
            
            if is_unknown_company:
                contact_status = "COMPANY_IDENTITY_REQUIRED"
                telemetry["identity_required_events"] += 1
            elif company not in company_discovery_status:
                contact_status = "BATCH_7_OUTCOME_MISSING"
                telemetry["missing_batch_7_outcome_events"] += 1
            else:
                discovery_outcome = company_discovery_status[company]
                
                # Explicit allowlist
                known_completed = ["COMPLETED", "NO_VERIFIED_PHONE"]
                known_incomplete = ["INCOMPLETE", "CONTACT_DISCOVERY_INCOMPLETE", "API_RATE_LIMIT", "NETWORK_FAILURE"]
                
                if company_to_verified.get(company):
                    contact_status = "VERIFIED_RECRUITMENT_CONTACT"
                    for vc in company_to_verified[company]:
                        linked_contact_ids.append(vc.get("contact_id"))
                elif discovery_outcome in known_incomplete:
                    contact_status = "CONTACT_DISCOVERY_INCOMPLETE"
                    telemetry["incomplete_contact_discovery_events"] += 1
                elif discovery_outcome in known_completed:
                    contact_status = "NO_VERIFIED_PUBLIC_RECRUITMENT_PHONE"
                    telemetry["no_phone_events"] += 1
                else:
                    contact_status = "BATCH_7_OUTCOME_INVALID"
                    telemetry["invalid_batch_7_outcome_events"] += 1
                
            canonical_id = event.get("canonical_identity") or event.get("event_id")
            if linked_contact_ids:
                for oc in outreach_contacts:
                    if oc["contact_id"] in linked_contact_ids:
                        if canonical_id not in oc["linked_event_ids"]:
                            oc["linked_event_ids"].append(canonical_id)
                            telemetry["verified_contacts_linked"] += 1

            # Priority 
            priority = "P3"
            priority_reason = ""
            
            if is_unknown_company:
                priority = "P3"
                priority_reason = "Unresolved company identity"
            elif target_fit == "FILTERED_OUT":
                priority = "P3"
                priority_reason = "Target fit is FILTERED_OUT"
            elif temporal_status == "HOT_OUTREACH_LEAD":
                if target_fit == "REVIEW":
                    priority = "P2"
                    priority_reason = "HOT_OUTREACH_LEAD but target fit needs REVIEW"
                else:
                    priority = "P0"
                    priority_reason = "HOT_OUTREACH_LEAD with valid company and target fit"
            elif temporal_status == "ACTIVE_OPPORTUNITY":
                if target_fit == "QUALIFIED":
                    priority = "P1"
                    priority_reason = "ACTIVE_OPPORTUNITY with QUALIFIED target fit"
                elif target_fit == "REVIEW":
                    priority = "P2"
                    priority_reason = "ACTIVE_OPPORTUNITY but target fit needs REVIEW"
                else:
                    priority = "P3"
                    priority_reason = "ACTIVE_OPPORTUNITY but target fit not qualified/review"
            else:
                priority = "P3"
                priority_reason = "Not actionable temporal status or unresolved"
                
            if target_fit == "FILTERED_OUT":
                telemetry["filtered_out_events"] += 1

            # Readiness
            readiness = "BLOCKED"
            readiness_reason = ""
            
            if is_unknown_company:
                readiness = "BLOCKED"
                readiness_reason = "COMPANY_IDENTITY_REQUIRED"
            elif target_fit == "REVIEW" or role_relevance == "UNKNOWN":
                readiness = "REVIEW"
                readiness_reason = "Important business dimensions remain unresolved (REVIEW/UNKNOWN)"
            elif priority in ["P0", "P1"]:
                if contact_status == "VERIFIED_RECRUITMENT_CONTACT":
                    readiness = "READY"
                    readiness_reason = "Known actionable event with verified recruitment contact"
                else:
                    readiness = "PARTIAL"
                    readiness_reason = "Known actionable event but lacking verified recruitment contact"
            else:
                readiness = "REVIEW" if priority == "P2" else "BLOCKED"
                readiness_reason = "Priority is not high enough for READY/PARTIAL"

            # Lead construction
            lead = {
                "canonical_event_id": canonical_id,
                "company_name": event.get("company_name"),
                "role": event.get("role"),
                "batch": event.get("batch"),
                "branches": event.get("eligible_branches", []),
                "ctc": event.get("ctc"),
                "event_date": event.get("event_date"),
                "registration_deadline": event.get("registration_deadline"),
                "role_relevance": bc.get("role_relevance"),
                "fresher_scope": bc.get("fresher_scope"),
                "branch_qualification": bc.get("branch_qualification"),
                "package_qualification": bc.get("package_qualification"),
                "target_fit": bc.get("target_fit"),
                "temporal_status": bc.get("temporal_status"),
                
                "outreach_priority": priority,
                "outreach_readiness": readiness,
                "contact_status": contact_status,
                "verified_contact_ids": linked_contact_ids,
                "priority_reason": priority_reason,
                "readiness_reason": readiness_reason,
                
                "source_lineage": {
                    "event_id": event.get("event_id"),
                    "source_event_id": event.get("source_event_id"),
                    "canonical_identity": event.get("canonical_identity"),
                    "batch_6_classification": bc,
                    "batch_7_discovery_outcome": company_discovery_status.get(company) if company else None
                }
            }
            
            if target_fit == "FILTERED_OUT":
                continue

            outreach_leads.append(lead)
            telemetry["events_emitted"] += 1
            telemetry["events_by_priority"][priority] += 1
            telemetry["events_by_readiness"][readiness] += 1
            
        except Exception as e:
            logging.error(f"Error processing event {event.get('event_id')}: {e}")
            telemetry["exceptions"] += 1
            telemetry["stop_reason"] = "EXCEPTION"

    # Write output files
    with open(out_leads_path, "w", encoding="utf-8") as f:
        json.dump(outreach_leads, f, indent=2)
    with open(out_contacts_path, "w", encoding="utf-8") as f:
        json.dump(outreach_contacts, f, indent=2)
    # Perform final serialized output validation before writing telemetry so the
    # telemetry artifact includes any validation failure and final stop reason.
    serialized_valid, serialized_error = validate_serialized_output(events_path, out_leads_path)
    if not serialized_valid:
        logging.error(f"Serialized output validation failed: {serialized_error}")
        telemetry["exceptions"] += 1
        if telemetry["stop_reason"] == "COMPLETED":
            telemetry["stop_reason"] = "SERIALIZED_OUTPUT_VALIDATION_FAILED"
        coverage_error = coverage_error or serialized_error

    recon_report = f"""# Batch 8 Reconciliation

Input canonical events = {telemetry['events_processed']}
Output outreach leads = {telemetry['events_emitted']}
Explicitly excluded events = {telemetry['events_processed'] - telemetry['events_emitted']}

## Contact Reconciliation
Events with verified contacts = {sum(1 for l in outreach_leads if l['contact_status'] == 'VERIFIED_RECRUITMENT_CONTACT')}
Events with NO verified phone = {telemetry['no_phone_events']}
Events with incomplete discovery = {telemetry['incomplete_contact_discovery_events']}
Events requiring company identity = {telemetry['identity_required_events']}
Events with missing Batch 7 outcome = {telemetry['missing_batch_7_outcome_events']}
Events with invalid Batch 7 outcome = {telemetry['invalid_batch_7_outcome_events']}
Total output events = {telemetry['events_emitted']}

## Priority Reconciliation
P0 = {telemetry['events_by_priority']['P0']}
P1 = {telemetry['events_by_priority']['P1']}
P2 = {telemetry['events_by_priority']['P2']}
P3 = {telemetry['events_by_priority']['P3']}
Total Priority = {sum(telemetry['events_by_priority'].values())}

## Readiness Reconciliation
READY = {telemetry['events_by_readiness']['READY']}
PARTIAL = {telemetry['events_by_readiness']['PARTIAL']}
REVIEW = {telemetry['events_by_readiness']['REVIEW']}
BLOCKED = {telemetry['events_by_readiness']['BLOCKED']}
Total Readiness = {sum(telemetry['events_by_readiness'].values())}
"""
    with open(out_recon_path, "w", encoding="utf-8") as f:
        f.write(recon_report)

    # Validate conditions
    is_pass = True
    if telemetry['exceptions'] > 0: is_pass = False
    if telemetry['missing_batch_7_outcome_events'] > 0: is_pass = False
    if telemetry['invalid_batch_7_outcome_events'] > 0: is_pass = False
    if sum(telemetry['events_by_priority'].values()) != telemetry['events_emitted']: is_pass = False
    if sum(telemetry['events_by_readiness'].values()) != telemetry['events_emitted']: is_pass = False
    if not serialized_valid: is_pass = False
    
    contact_status_sum = (sum(1 for l in outreach_leads if l['contact_status'] == 'VERIFIED_RECRUITMENT_CONTACT') +
                         telemetry['no_phone_events'] +
                         telemetry['incomplete_contact_discovery_events'] +
                         telemetry['identity_required_events'] +
                         telemetry['missing_batch_7_outcome_events'] +
                         telemetry['invalid_batch_7_outcome_events'])

    
    # Persist final telemetry only after serialization validation has updated it.
    with open(out_telemetry_path, "w", encoding="utf-8") as f:
        json.dump(telemetry, f, indent=2)

    val_report = f"""# Batch 8 Final Validation

Execution Date: {datetime.utcnow().isoformat()}Z

## A. Summary
- Processed: {telemetry['events_processed']}
- Emitted: {telemetry['events_emitted']}
- Exceptions: {telemetry['exceptions']}
- Stop Reason: {telemetry['stop_reason']}

## Rules documented
- Priority P0: HOT_OUTREACH_LEAD with valid company and target fit
- Priority P1: ACTIVE_OPPORTUNITY with QUALIFIED target fit
- Priority P2: HOT or ACTIVE but target fit needs REVIEW
- Priority P3: Unresolved identity, FILTERED_OUT, or other temporal status

## Coverage Error
{coverage_error if coverage_error else "None"}

BATCH 8 = {"PASS" if is_pass else "HOLD"}
"""
    with open(out_val_path, "w", encoding="utf-8") as f:
        f.write(val_report)

    return is_pass

if __name__ == "__main__":
    success = run_batch_8()
    sys.exit(0 if success else 1)
