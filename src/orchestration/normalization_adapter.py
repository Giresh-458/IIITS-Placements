import hashlib
from typing import List, Dict, Any
from datetime import datetime
import os

from src.models.domain import HiringEventCandidate, NormalizedHiringEvent
from src.normalization.company_normalizer import normalize_company
from src.normalization.role_normalizer import normalize_role
from src.normalization.branch_normalizer import normalize_branch
from src.normalization.compensation_normalizer import normalize_compensation
from src.normalization.batch_mode_normalizer import normalize_batch, normalize_campus_mode
from src.normalization.eligibility_normalizer import normalize_eligibility
from src.normalization.date_normalizer import normalize_dates

def generate_deterministic_id(identity: str) -> str:
    return hashlib.sha256(identity.encode('utf-8')).hexdigest()

def normalize_candidates(candidates: List[HiringEventCandidate]) -> List[NormalizedHiringEvent]:
    dedup_map = {}
    
    for row in candidates:
        inst = row.institution
        raw_comp = row.company_name or ""
        raw_role = row.role or ""
        raw_branches = ", ".join(row.eligible_branches) if row.eligible_branches else ""
        raw_batch = row.batch or ""
        raw_ctc = row.ctc_raw if row.ctc_raw else (str(row.ctc) if row.ctc else "")
        raw_date_text = row.event_date_raw or (row.event_date.isoformat() if row.event_date else "")
        raw_reg = row.registration_deadline_raw or (row.registration_deadline.isoformat() if row.registration_deadline else "")
        raw_campus = row.campus_mode or ""
        
        if not (raw_comp or raw_role or raw_branches or raw_batch or raw_ctc or raw_date_text or raw_reg):
            continue
            
        source_url = row.event_url or row.source_seed_url
        # Keep the detail page and discovery seed as provenance. A normalized
        # event can be deduplicated from multiple pages, so source_urls is a
        # unique union of every contributing detail/seed URL.
        source_urls = list(dict.fromkeys(
            url for url in (row.event_url, row.source_seed_url) if url
        ))

        evidence_raw_values = {
            "company": raw_comp,
            "role": raw_role,
            "branch": raw_branches,
            "batch": raw_batch,
            "ctc": raw_ctc,
            "event_date": raw_date_text,
            "registration_deadline": raw_reg,
            "campus_mode": raw_campus,
        }
        normalized_evidence = []
        for evidence_field, source_evidence in (row.evidence or {}).items():
            if not isinstance(source_evidence, dict):
                continue
            normalized_evidence.append({
                "field": evidence_field,
                "raw_value": evidence_raw_values.get(evidence_field),
                "evidence_url": source_url or None,
                "evidence_text": source_evidence.get("text") or source_evidence.get("evidence_text"),
                "extraction_method": source_evidence.get("method") or source_evidence.get("extraction_method"),
                "confidence": source_evidence.get("confidence"),
            })

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
        
        id_comp = comp_norm if comp_norm != "UNKNOWN" else "UNKNOWN"
        id_date = ev_date if ev_date else "UNKNOWN"
        id_inst = inst
        
        identity = f"{id_inst}|{id_comp}|{id_date}"
        
        if comp_norm == "UNKNOWN":
            id_role = role_fam if role_fam != "UNKNOWN" else "UNKNOWN"
            id_url = source_url
            identity = f"{id_inst}|{id_comp}|{id_role}|{id_date}|{id_url}"
            
        from src.normalization.event_validator import validate_event_candidate
        status = validate_event_candidate(
            comp_norm=comp_norm if comp_norm != "UNKNOWN" else None,
            role_fam=role_fam if role_fam != "UNKNOWN" else None,
            ctc_amt=ctc_amt,
            reg_date=reg_date,
            ev_date=ev_date,
            batch_norm=batch_norm,
            campus_mode=campus_mode,
            raw_event_text=row.raw_text_excerpt
        )
        
        event_dict = {
            "event_id": generate_deterministic_id(identity),
            "canonical_identity": identity,
            "source_event_id": row.event_id,
            "event_status": status,
            "institution": inst,
            "source_seed_id": None,
            "source_seed_url": row.source_seed_url or None,
            "source_urls": source_urls,
            "company_name": comp_norm if comp_norm != "UNKNOWN" else None,
            "company_name_raw": raw_comp,
            "company_aliases": comp_aliases,
            "event_title": row.event_title,
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
            "event_date": ev_date if ev_date else None,
            "event_date_raw": raw_date_text,
            "event_date_confidence": "HIGH" if ev_date else "UNKNOWN",
            "registration_deadline": reg_date if reg_date else None,
            "registration_deadline_raw": raw_reg,
            "campus_mode": campus_mode,
            "campus_mode_raw": raw_campus,
            "event_type": event_type,
            "event_url": source_url,
            # Do not copy row.raw_text_excerpt into raw_event_text: the source
            # can contain unrelated roster/contact data. Preserve only the
            # field-specific extraction evidence already captured upstream.
            "evidence": normalized_evidence,
            "is_recent": False
        }
        
        if ev_date:
            mock_curr = os.environ.get("MOCK_CURRENT_DATE", datetime.utcnow().isoformat()[:10])
            try:
                dt_ev = datetime.fromisoformat(ev_date)
                dt_curr = datetime.fromisoformat(mock_curr)
                if (dt_curr - dt_ev).days <= 30:
                    event_dict["is_recent"] = True
            except:
                pass
                
        event_dict["_discovered_at"] = row.discovered_at

        if identity in dedup_map:
            existing = dedup_map[identity]
            # Preserve provenance from every candidate folded into this
            # canonical event rather than keeping only the first page's trace.
            existing["source_urls"] = list(dict.fromkeys(
                (existing.get("source_urls") or []) + (event_dict.get("source_urls") or [])
            ))
            if not existing.get("source_seed_url") and event_dict.get("source_seed_url"):
                existing["source_seed_url"] = event_dict["source_seed_url"]
            for evidence_item in event_dict.get("evidence") or []:
                if evidence_item not in existing.setdefault("evidence", []):
                    existing["evidence"].append(evidence_item)

            if not existing["company_name"] and event_dict["company_name"]: existing["company_name"] = event_dict["company_name"]
            if not existing["role"] and event_dict["role"]:
                existing["role"] = event_dict["role"]
                existing["role_family"] = event_dict["role_family"]
            if not existing["batch"] and event_dict["batch"]: existing["batch"] = event_dict["batch"]
            
            # CTC conflict resolution
            if event_dict["ctc"]:
                if not existing["ctc"]:
                    existing["ctc"] = event_dict["ctc"]
                    existing["ctc_raw"] = event_dict["ctc_raw"]
                elif existing["ctc"] != event_dict["ctc"]:
                    # Preserve conflict
                    existing.setdefault("evidence", []).append({
                        "type": "ctc_conflict",
                        "value": event_dict["ctc"],
                        "raw": event_dict["ctc_raw"],
                        "url": event_dict["event_url"]
                    })
                    # Fresher source wins
                    if event_dict["_discovered_at"] > existing["_discovered_at"]:
                        # Move existing to conflict and promote new
                        existing["evidence"].append({
                            "type": "ctc_conflict",
                            "value": existing["ctc"],
                            "raw": existing["ctc_raw"],
                            "url": existing["event_url"]
                        })
                        existing["ctc"] = event_dict["ctc"]
                        existing["ctc_raw"] = event_dict["ctc_raw"]
                        existing["_discovered_at"] = event_dict["_discovered_at"]

            if (not existing.get("event_date")) and (event_dict.get("event_date")):
                existing["event_date"] = event_dict["event_date"]
                existing["event_date_raw"] = event_dict["event_date_raw"]
            for b in event_dict["eligible_branches"]:
                if b not in existing["eligible_branches"]:
                    existing["eligible_branches"].append(b)
        else:
            dedup_map[identity] = event_dict
            
    # Clean up temporary fields
    for e in dedup_map.values():
        e.pop("_discovered_at", None)
        
    return [NormalizedHiringEvent(**e) for e in dedup_map.values()]
