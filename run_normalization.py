import json
import uuid
import sys
import os
import hashlib
from datetime import datetime
from src.normalization.company_normalizer import normalize_company
from src.normalization.role_normalizer import normalize_role
from src.normalization.branch_normalizer import normalize_branch
from src.normalization.compensation_normalizer import normalize_compensation
from src.normalization.batch_mode_normalizer import normalize_batch, normalize_campus_mode
from src.normalization.eligibility_normalizer import normalize_eligibility
from src.normalization.date_normalizer import normalize_dates

def generate_deterministic_id(identity: str) -> str:
    return hashlib.sha256(identity.encode('utf-8')).hexdigest()

def create_evidence(field: str, raw_value: str, normalized_value: str, url: str, text: str, method: str, confidence: str) -> dict:
    return {
        "field": field,
        "raw_value": raw_value,
        "normalized_value": normalized_value,
        "evidence_url": url,
        "evidence_text": text,
        "extraction_method": method,
        "confidence": confidence
    }

def run_normalization():
    with open('artifacts/recovered_event_extractions.json') as f:
        raw_events = json.load(f)
        
    dedup_map = {}
    
    for row in raw_events:
        inst = row.get("institution", "UNKNOWN")
        raw_comp = row.get("company_candidate") or ""
        raw_role = row.get("role_candidate") or ""
        raw_branches = row.get("branch_candidate") or ""
        raw_batch = row.get("batch_candidate") or ""
        raw_ctc = row.get("ctc_candidate") or ""
        raw_cgpa = "" # Not in standard candidates list here
        raw_date_text = row.get("event_date_candidate") or ""
        raw_reg = row.get("registration_deadline_candidate") or ""
        raw_campus = row.get("campus_mode_candidate") or ""
        
        # Check if they are all empty
        if not (raw_comp or raw_role or raw_branches or raw_batch or raw_ctc or raw_date_text or raw_reg):
            continue
            
        source_url = row.get("event_url") or ""
        
        comp_norm, comp_aliases, comp_warnings, comp_valid = normalize_company(raw_comp)
        if not comp_norm: comp_norm = "UNKNOWN"
        
        role_fam, role_sub, role_warn, role_valid = normalize_role(raw_role)
        if not role_fam: role_fam = "UNKNOWN"
        
        branch_norm = normalize_branch([raw_branches] if raw_branches else [])
        batch_norm, batch_warn = normalize_batch(raw_batch)
        
        ctc_amt, ctc_curr, ctc_unit, ctc_per, ctc_warn = normalize_compensation(raw_ctc, "")
        
        ev_date, reg_date, pub_date, mod_date, end_date, date_warn = normalize_dates(raw_date_text, "")
        if raw_reg and not reg_date:
            _, reg_date2, _, _, _, _ = normalize_dates(raw_reg, "")
            if reg_date2: reg_date = reg_date2
            
        campus_mode = normalize_campus_mode(raw_campus, "")
        event_type = "RECRUITMENT_DRIVE" if comp_norm != "UNKNOWN" else "UNKNOWN"
        
        # Build identity
        id_comp = comp_norm if comp_norm != "UNKNOWN" else "UNKNOWN"
        id_date = ev_date if ev_date else "UNKNOWN"
        id_inst = inst
        
        identity = f"{id_inst}|{id_comp}|{id_date}"
        
        if comp_norm == "UNKNOWN":
            id_role = role_fam if role_fam != "UNKNOWN" else "UNKNOWN"
            id_url = source_url
            identity = f"{id_inst}|{id_comp}|{id_role}|{id_date}|{id_url}"
        
        event = {
            "event_id": generate_deterministic_id(identity),
            "canonical_identity": identity,
            "source_event_id": row.get("source_event_id"),
            "institution": inst,
            "institution_id": None,
            "source_seed_id": None,
            "company_name": comp_norm if comp_norm != "UNKNOWN" else None,
            "company_name_raw": raw_comp,
            "company_aliases": comp_aliases,
            "event_title": None,
            "event_title_raw": None,
            "role": role_fam if role_fam != "UNKNOWN" else None,
            "role_raw": raw_role,
            "role_family": role_fam,
            "role_subtype": role_sub,
            "eligible_branches": list(branch_norm),
            "eligible_branches_raw": raw_branches,
            "branch_groups": list(branch_norm),
            "batch": str(batch_norm) if batch_norm else None,
            "batch_raw": raw_batch,
            "graduation_year": batch_norm,
            "ctc": ctc_amt,
            "ctc_raw": raw_ctc,
            "ctc_currency": ctc_curr,
            "ctc_unit": ctc_unit,
            "ctc_period": ctc_per,
            "cgpa_requirement": None,
            "cgpa_raw": None,
            "event_date": ev_date if ev_date else "UNKNOWN",
            "event_date_raw": raw_date_text,
            "event_date_confidence": "HIGH" if ev_date else "UNKNOWN",
            "registration_deadline": reg_date if reg_date else None,
            "registration_deadline_raw": raw_reg,
            "registration_deadline_confidence": "UNKNOWN",
            "campus_mode": campus_mode,
            "campus_mode_raw": raw_campus,
            "event_type": event_type,
            "event_url": source_url,
            "evidence": [],
            "is_recent": False
        }
        
        if ev_date:
            mock_curr = os.environ.get("MOCK_CURRENT_DATE", datetime.utcnow().isoformat()[:10])
            try:
                dt_ev = datetime.fromisoformat(ev_date)
                dt_curr = datetime.fromisoformat(mock_curr)
                if (dt_curr - dt_ev).days <= 30:
                    event["is_recent"] = True
            except:
                pass
        
        if identity in dedup_map:
            existing = dedup_map[identity]
            if not existing["company_name"] and event["company_name"]: existing["company_name"] = event["company_name"]
            if not existing["role"] and event["role"]:
                existing["role"] = event["role"]
                existing["role_family"] = event["role_family"]
            if not existing["batch"] and event["batch"]: existing["batch"] = event["batch"]
            if not existing["ctc"] and event["ctc"]: existing["ctc"] = event["ctc"]
            if (not existing.get("event_date") or existing.get("event_date") == "UNKNOWN") and (event.get("event_date") != "UNKNOWN"):
                existing["event_date"] = event["event_date"]
                existing["event_date_raw"] = event["event_date_raw"]
            for b in event["eligible_branches"]:
                if b not in existing["eligible_branches"]:
                    existing["eligible_branches"].append(b)
        else:
            dedup_map[identity] = event

    out_events = list(dedup_map.values())
    
    with open('artifacts/normalized_hiring_events.json', 'w', encoding='utf-8') as f:
        json.dump(out_events, f, indent=2)

    with open('artifacts/normalization_telemetry.json', 'w', encoding='utf-8') as f:
        json.dump({"events_after_dedup": len(out_events)}, f)

if __name__ == '__main__':
    run_normalization()
