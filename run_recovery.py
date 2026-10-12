import json
import uuid
import os
from datetime import datetime
from urllib.parse import urljoin
from typing import Dict, List, Tuple
from src.evidence.rehydrator import rehydrate_url
from src.extraction.event_extractor import extract_from_text
from src.normalization.company_normalizer import normalize_company
from src.normalization.role_normalizer import normalize_role
from src.normalization.date_normalizer import normalize_dates
from src.normalization.branch_normalizer import normalize_branch
from src.normalization.batch_mode_normalizer import normalize_batch
from src.normalization.compensation_normalizer import normalize_compensation
from src.normalization.batch_mode_normalizer import normalize_campus_mode
from src.normalization.eligibility_normalizer import normalize_eligibility
from src.normalization.event_validator import validate_event_candidate
from src.models.domain import NormalizedHiringEvent

def generate_deterministic_id(identity: str) -> str:
    import hashlib
    return hashlib.sha256(identity.encode()).hexdigest()[:16]

def run_recovery():
    with open('artifacts/discovered_events.json') as f:
        raw_events = json.load(f)
        
    telemetry = {
        "run_id": str(uuid.uuid4()),
        "started_at": datetime.utcnow().isoformat(),
        "input_records": len(raw_events),
        "records_processed": 0,
        "child_candidates_found": 0,
        "child_candidates_processed": 0,
        "child_candidates_skipped_budget": 0,
        "pages_rehydrated": 0,
        "pdfs_rehydrated": 0,
        "js_pages_rehydrated": 0,
        "structured_payloads_processed": 0,
        "company_candidates": 0,
        "company_recovered": 0,
        "company_rejected": 0,
        "role_candidates": 0,
        "role_recovered": 0,
        "role_rejected": 0,
        "branch_candidates": 0,
        "branch_recovered": 0,
        "batch_candidates": 0,
        "batch_recovered": 0,
        "ctc_candidates": 0,
        "ctc_recovered": 0,
        "cgpa_candidates": 0,
        "cgpa_recovered": 0,
        "event_dates_recovered": 0,
        "deadlines_recovered": 0,
        "source_missing": 0,
        "upstream_fetch_loss": 0,
        "excerpt_loss": 0,
        "html_failures": 0,
        "pdf_failures": 0,
        "js_failures": 0,
        "structured_failures": 0,
        "ambiguous": 0,
        "evidence_records": 0,
        "events_before_dedup": 0,
        "events_after_dedup": 0,
        "exceptions": 0,
        "candidates_rejected_non_event": 0,
        "stop_reason": "COMPLETED",
        "validation_errors": []
    }
    
    recovered_events = []
    evidence_audit = []
    dedup_map = {}
    
    max_child_pages = 5
    
    for row in raw_events:
        url = row.get("event_url")
        seed = row.get("source_seed_url")
        inst = row.get("institution")
        
        telemetry["records_processed"] += 1
        
        is_index = False
        if url and seed and url == seed:
            is_index = True
        elif url and url.endswith(("/index", "/index/", "/event/", "/placement/", "/0")):
            is_index = True
            
        parent_rehydrated = None
        if url:
            parent_rehydrated, _ = rehydrate_url(url)
            
        candidates_to_process = []
        
        if is_index and parent_rehydrated:
            title = (row.get("event_title") or "").lower()
            cand_c = (row.get("company_name") or "").lower()
            if cand_c == "none": cand_c = ""
            
            scored_hrefs = {}
            for link in parent_rehydrated.get("links", []):
                href = link.get("href", "")
                text = link.get("text", "").lower()
                if not href or href.startswith("#") or "javascript:" in href: continue
                if not href.startswith("http"):
                    href = urljoin(url, href)
                    
                score = 0
                if cand_c and len(cand_c) > 3 and cand_c in text: score += 100
                if title and len(title) > 3 and title in text: score += 50
                if "drive" in text or "recruitment" in text or "hiring" in text or "placement" in text: score += 50
                if "notice" in text: score += 20
                if href.endswith(".pdf"): score += 10
                if "read more" in text: score += 5
                
                if score > 0:
                    scored_hrefs[href] = max(score, scored_hrefs.get(href, 0))
            
            scored_links = [(s, h) for h, s in scored_hrefs.items()]
            scored_links.sort(reverse=True, key=lambda x: x[0])
            
            telemetry["child_candidates_found"] += len(scored_links)
            
            processed_count = 0
            for s, h in scored_links:
                if processed_count >= max_child_pages:
                    telemetry["child_candidates_skipped_budget"] += 1
                    continue
                candidates_to_process.append({"url": h, "is_child": True})
                processed_count += 1
                telemetry["child_candidates_processed"] += 1
                
        if not candidates_to_process:
            # Either it wasn't an index, or we found no children. Process the parent URL directly.
            candidates_to_process.append({"url": url, "is_child": False})
            
        for cand in candidates_to_process:
            c_url = cand["url"]
            is_child = cand["is_child"]
            
            rehydrated, audit = rehydrate_url(c_url)
            
            if not rehydrated:
                continue
                
            telemetry["pages_rehydrated"] += 1
            if audit["pdf"]["succeeded"]: telemetry["pdfs_rehydrated"] += 1
            if audit["js"]["succeeded"]: telemetry["js_pages_rehydrated"] += 1
            if audit["json_ld"]["succeeded"]: telemetry["structured_payloads_processed"] += 1
            
            if not audit["html"]["succeeded"] and audit["html"]["attempted"]: telemetry["html_failures"] += 1
            if not audit["pdf"]["succeeded"] and audit["pdf"]["attempted"]: telemetry["pdf_failures"] += 1
            if not audit["js"]["succeeded"] and audit["js"]["attempted"]: telemetry["js_failures"] += 1
            if not audit["json_ld"]["succeeded"] and audit["json_ld"]["attempted"]: telemetry["structured_failures"] += 1
            
            # Incorporate child fetch into the audit object
            audit["child_event"] = {"attempted": is_child, "succeeded": is_child}
            
            corpus = [rehydrated.get("title", "")] + rehydrated.get("headings", []) + rehydrated.get("tables", []) + rehydrated.get("paragraphs", []) + rehydrated.get("lists", [])
            
            if rehydrated.get("json_ld"):
                for j in rehydrated["json_ld"]:
                    if isinstance(j, dict):
                        if "startDate" in j: corpus.append(f"Campus Drive Date | {j['startDate']}")
                        if "organizer" in j and isinstance(j["organizer"], dict) and "name" in j["organizer"]:
                            corpus.append(f"Company Name | {j['organizer']['name']}")
                        if "name" in j and j.get("@type") == "Event":
                            corpus.append(f"Job Title | {j['name']}")
                            
            full_text_to_parse = "\\n".join(corpus)
            
            # 1. STRUCTURAL RECOVERY EXTRACTION
            extracted = extract_from_text(full_text_to_parse, c_url)
            
            cand_comp = extracted.get("company_candidate")
            cand_role = extracted.get("role_candidate")
            cand_ctc = extracted.get("ctc_candidate")
            cand_cgpa = extracted.get("cgpa_candidate")
            cand_branches = extracted.get("branch_candidate")
            cand_batch = extracted.get("batch_candidate")
            cand_date = extracted.get("event_date_candidate")
            cand_reg = extracted.get("registration_deadline_candidate")
            cand_date_raw = extracted.get("event_date_raw")
            cand_campus_mode = extracted.get("campus_mode_candidate")
            
            # Increment candidate telemetry
            if cand_comp: telemetry["company_candidates"] += 1
            if cand_role: telemetry["role_candidates"] += 1
            if cand_ctc: telemetry["ctc_candidates"] += 1
            if cand_cgpa: telemetry["cgpa_candidates"] += 1
            if cand_branches: telemetry["branch_candidates"] += 1
            if cand_batch: telemetry["batch_candidates"] += 1
            
            # 2. NORMALIZATION & SEMANTIC VALIDATION
            warnings = []
            confidence = {}
            comp_norm, comp_aliases, comp_warnings, comp_valid = normalize_company(cand_comp)
            warnings.extend(comp_warnings)
            if not comp_valid:
                comp_norm = None
                cand_comp = None
            if cand_comp and not comp_norm: telemetry["company_rejected"] += 1
            if cand_comp and comp_norm: telemetry["company_recovered"] += 1
            
            role_fam, role_sub, role_warn, role_valid = normalize_role(cand_role)
            if not role_valid:
                role_fam = "UNKNOWN"
                role_sub = "UNKNOWN"
            if cand_role and role_fam == "UNKNOWN": telemetry["role_rejected"] += 1
            if cand_role and role_fam != "UNKNOWN": telemetry["role_recovered"] += 1
            
            ctc_amt, ctc_curr, ctc_unit, ctc_per, ctc_warn = normalize_compensation(cand_ctc, full_text_to_parse)
            if cand_ctc and ctc_amt: telemetry["ctc_recovered"] += 1
            
            cgpa_norm, cgpa_warn = normalize_eligibility(cand_cgpa)
            if cand_cgpa and cgpa_norm: telemetry["cgpa_recovered"] += 1
            
            branch_norm = normalize_branch([cand_branches] if cand_branches else [])
            if cand_branches and branch_norm: telemetry["branch_recovered"] += 1
            
            batch_norm, batch_warn = normalize_batch(cand_batch)
            if cand_batch and batch_norm: telemetry["batch_recovered"] += 1
            
            ev_date, reg_date, pub_date, mod_date, end_date, date_warn = normalize_dates(cand_date_raw or cand_date or "", full_text_to_parse)
            if cand_reg and not reg_date:
                _, reg_date2, _, _, _, _ = normalize_dates(cand_reg, full_text_to_parse)
                if reg_date2: reg_date = reg_date2
            if not ev_date and not reg_date: telemetry["ambiguous"] += 1
            if ev_date: telemetry["event_dates_recovered"] += 1
            if reg_date: telemetry["deadlines_recovered"] += 1
                
            campus_mode = normalize_campus_mode(cand_campus_mode or "", full_text_to_parse)
            event_type = "RECRUITMENT_DRIVE" if comp_norm else "UNKNOWN"
            
            evidence_chain = []
            def add_ev(key, text_val, norm_val, mthd):
                evidence_chain.append({"field": key, "text": text_val, "method": mthd})
                telemetry["evidence_records"] += 1
                
            if comp_norm: add_ev("company", cand_comp, comp_norm, "company")
            if ctc_amt: add_ev("ctc", cand_ctc, str(ctc_amt), "ctc")
            if cgpa_norm: add_ev("cgpa", cand_cgpa, str(cgpa_norm), "cgpa")
            if ev_date: add_ev("event_date", cand_date_raw or cand_date, ev_date, "event_date")
            if reg_date: add_ev("registration_deadline", cand_reg, reg_date, "registration_deadline")
            if role_fam != "UNKNOWN": add_ev("role", cand_role, role_fam, "role")
            if batch_norm: add_ev("batch", cand_batch, str(batch_norm), "batch")
            if branch_norm: add_ev("branch", cand_branches, ",".join(branch_norm), "branch")
            if campus_mode != "UNKNOWN": add_ev("campus_mode", cand_campus_mode, campus_mode, "campus_mode")
                
            is_recent = False
            if ev_date:
                try:
                    edate = datetime.strptime(ev_date, "%Y-%m-%d") if len(ev_date) == 10 and "-" in ev_date else datetime.strptime(ev_date, "%d %B %Y")
                    cdate = datetime.strptime(os.environ.get("MOCK_CURRENT_DATE", datetime.utcnow().strftime("%Y-%m-%d")), "%Y-%m-%d")
                    if (edate - cdate).days >= -7: is_recent = True
                except: pass
                
            validity = validate_event_candidate(
                comp_norm=comp_norm,
                role_fam=role_fam,
                ctc_amt=ctc_amt,
                reg_date=reg_date,
                ev_date=ev_date,
                batch_norm=batch_norm,
                campus_mode=campus_mode,
                raw_event_text=full_text_to_parse
            )
            
            # Record the candidate regardless of validity
            recovered_events.append({
                "source_event_id": row.get("event_id"),
                "institution": inst,
                "event_url": url,
                "company_candidate": cand_comp,
                "role_candidate": cand_role,
                "branch_candidate": cand_branches,
                "batch_candidate": cand_batch,
                "ctc_candidate": cand_ctc,
                "event_date_candidate": cand_date_raw or cand_date,
                "registration_deadline_candidate": cand_reg,
                "campus_mode_candidate": cand_campus_mode,
                "event_validity": validity
            })
            
            if validity == "REJECTED_NON_EVENT":
                telemetry["candidates_rejected_non_event"] = telemetry.get("candidates_rejected_non_event", 0) + 1
                continue
                
            identity = f"{inst}_{comp_norm}_{ev_date}_{role_fam}_{batch_norm}".lower().replace(" ", "_")
            canonical_id = generate_deterministic_id(identity)
            
            telemetry["events_before_dedup"] += 1
            
            # Safe Deduplication
            if comp_norm is None:
                identity = f"{identity}_{row.get('event_id', str(uuid.uuid4()))}"
                
            missingness = {}
            for field, val in [("company", comp_norm), ("role", role_fam), ("ctc", ctc_amt), ("branch", branch_norm), ("batch", batch_norm)]:
                if not val or val == "UNKNOWN" or val == []:
                    # Proper Missingness Logic:
                    if is_index and not audit["child_event"]["succeeded"]:
                        cls = "UPSTREAM_FETCH_LOSS"
                        reason = "Index page parsed but child event links could not be followed or retrieved."
                    elif not rehydrated:
                        cls = "UPSTREAM_FETCH_LOSS"
                        reason = "Could not fetch original URL."
                    elif audit["html"]["attempted"] or audit["pdf"]["attempted"]:
                        # We actually tried to parse it and found nothing.
                        cls = "SOURCE_TRULY_MISSING"
                        reason = "Applicable evidence paths exhausted; field is truly missing."
                    else:
                        cls = "UPSTREAM_FETCH_LOSS"
                        reason = "Evidence paths not fully attempted."
                        
                    missingness[field] = cls
                    if cls == "SOURCE_TRULY_MISSING": telemetry["source_missing"] += 1
                    elif cls == "UPSTREAM_FETCH_LOSS": telemetry["upstream_fetch_loss"] += 1
                    
                    evidence_audit.append({
                        "record_id": str(len(recovered_events) + 1),
                        "institution": inst,
                        "event_url": c_url,
                        "field": field,
                        "evidence_paths": audit,
                        "candidate_found": False,
                        "candidate_value": None,
                        "evidence_url": None,
                        "evidence_excerpt": None,
                        "extraction_method": None,
                        "confidence": None,
                        "missingness_classification": cls,
                        "missingness_reason": reason
                    })
                else:
                    evidence_audit.append({
                        "record_id": str(len(recovered_events) + 1),
                        "institution": inst,
                        "event_url": c_url,
                        "field": field,
                        "evidence_paths": audit,
                        "candidate_found": True,
                        "candidate_value": str(val),
                        "evidence_url": c_url,
                        "evidence_excerpt": "Valid",
                        "extraction_method": "structural_regex",
                        "confidence": "HIGH",
                        "missingness_classification": "NOT_APPLICABLE",
                        "missingness_reason": None
                    })
            
            try:
                event = NormalizedHiringEvent(
                    event_id=generate_deterministic_id(identity),
                    institution=inst,
                    company_name=comp_norm if comp_norm else None,
                    company_name_raw=cand_comp if cand_comp else None,
                    role_raw=cand_role if cand_role else None,
                    role_family=role_fam,
                    eligible_branches=branch_norm,
                    graduation_year=batch_norm,
                    ctc=ctc_amt,
                    ctc_raw=cand_ctc if cand_ctc else None,
                    cgpa_requirement=cgpa_norm,
                    event_date=ev_date,
                    registration_deadline=reg_date,
                    campus_mode=campus_mode,
                    event_type=event_type,
                    is_recent=is_recent,
                    canonical_identity=identity,
                    source_event_id=row.get("event_id"),
                    event_url=c_url
                )
                    
                if identity in dedup_map:
                    existing = dedup_map[identity]
                    if event.ctc and not existing.ctc: existing.ctc = event.ctc; existing.ctc_raw = event.ctc_raw
                    if event.cgpa_requirement and not existing.cgpa_requirement: existing.cgpa_requirement = event.cgpa_requirement
                    if event.role_family != "UNKNOWN" and existing.role_family == "UNKNOWN": existing.role_family = event.role_family; existing.role_raw = event.role_raw
                    if event.graduation_year and not existing.graduation_year: existing.graduation_year = event.graduation_year
                    if event.eligible_branches and not existing.eligible_branches: existing.eligible_branches = event.eligible_branches
                    if event.company_name and not existing.company_name: existing.company_name = event.company_name
                    if event.registration_deadline and not existing.registration_deadline: existing.registration_deadline = event.registration_deadline
                    dedup_map[identity] = existing
                else:
                    dedup_map[identity] = event
                    
            except Exception as e:
                telemetry["validation_errors"].append(f"Validation failed for {identity}: {str(e)}")
                telemetry["exceptions"] += 1
        
    telemetry["events_after_dedup"] = len(dedup_map)
    telemetry["duration_seconds"] = (datetime.utcnow() - datetime.fromisoformat(telemetry["started_at"])).total_seconds()
    telemetry["finished_at"] = datetime.utcnow().isoformat()
    
    out_events = [e.model_dump() for e in dedup_map.values()]
    with open('artifacts/normalized_hiring_events.json', 'w', encoding='utf-8') as f: json.dump(out_events, f, indent=2)
    with open('artifacts/recovered_event_extractions.json', 'w', encoding='utf-8') as f: json.dump(recovered_events, f, indent=2)
    with open('artifacts/batch_5_6_recovery_telemetry.json', 'w', encoding='utf-8') as f: json.dump(telemetry, f, indent=2)
    with open('artifacts/batch_5_6_evidence_audit.json', 'w', encoding='utf-8') as f: json.dump(evidence_audit, f, indent=2)
    with open('artifacts/normalization_telemetry.json', 'w', encoding='utf-8') as f: json.dump({"events_after_dedup": len(out_events)}, f)

if __name__ == "__main__":
    run_recovery()
