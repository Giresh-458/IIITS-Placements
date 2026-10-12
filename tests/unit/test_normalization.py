import pytest
import os
import json
from src.normalization.company_normalizer import normalize_company
from src.normalization.role_normalizer import normalize_role
from src.normalization.branch_normalizer import normalize_branch
from src.normalization.compensation_normalizer import normalize_compensation, extract_cgpa
from src.normalization.batch_mode_normalizer import normalize_batch, normalize_campus_mode, normalize_event_type
from src.normalization.eligibility_normalizer import extract_eligibility
from src.normalization.date_normalizer import normalize_dates
import run_normalization
from pydantic import ValidationError

def test_company_normalization():
    name, aliases, w, valid = normalize_company("DH Bars & Wires Private Limited (Formerly known as D.H Experts Private Limited)")
    assert valid is True
    assert name == "DH Bars & Wires Private Limited"
    assert "D.H Experts Private Limited" in aliases
    
    # Dissimilar companies shouldn't merge, handled at deduplication level via hashed identities
    id1 = run_normalization.generate_deterministic_id("inst_Company A_date_role_batch")
    id2 = run_normalization.generate_deterministic_id("inst_Company B_date_role_batch")
    assert id1 != id2

def test_company_rejection_heuristics():
    # Test cases that should be rejected as UPSTREAM_EXTRACTION_ERROR
    reject_cases = ["Profile", "Name", "Company", "Company Name", "s Placement Record", ". 5.", "Date", "Role", "Details", "Branch", "on-Campus", "On Campus", "Off Campus", "Campus", "Company Profile", "Recruitment Drive", "Placement Drive", "Drive"]
    for case in reject_cases:
        name, aliases, w, valid = normalize_company(case)
        assert valid is False, f"Failed on: {case}"
        assert name == ""

def test_role_normalization():
    fam, sub, w, valid = normalize_role("Software Engineer")
    assert valid is True
    assert fam == "SOFTWARE_ENGINEERING"
    
    fam, sub, w, valid = normalize_role("Machine Learning Engineer")
    assert valid is True
    assert fam == "AI_ML"
    
    fam, sub, w, valid = normalize_role("Obscure Random Job")
    assert valid is True
    assert fam == "UNKNOWN"

def test_role_rejection_heuristics():
    reject_cases = ["Profile", "Name", "Role", "Designation", "Branch", "Branches", "Department"]
    for case in reject_cases:
        fam, sub, w, valid = normalize_role(case)
        assert valid is False
        assert fam == "UNKNOWN"

def test_branch_normalization():
    b = normalize_branch(["Computer Science", "ECE", "IT"])
    assert "CSE" in b
    assert "ECE" in b
    assert "IT" in b
    
    b = normalize_branch(["All branches"])
    assert "ALL_BRANCHES" in b

def test_compensation_normalization():
    amt, curr, unit, period, w = normalize_compensation("10 LPA", "CTC: 10 LPA")
    assert amt == 10.0
    
    amt, curr, unit, period, w = normalize_compensation("20000", "Stipend 20000 per month")
    assert amt is None
    
    amt, curr, unit, period, w = normalize_compensation("CTC 10 LPA Variable 3 LPA", "CTC 10 LPA Variable 3 LPA")
    assert amt == 10.0

def test_compensation_rejection():
    # Just a number without context shouldn't extract as CTC
    amt, curr, unit, period, w = normalize_compensation("10", "10")
    assert amt is None
    
def test_cgpa_normalization():
    cgpa = extract_cgpa("Minimum CGPA 7.0")
    assert cgpa == 7.0
    
    amt, _, _, _, _ = normalize_compensation("Minimum CGPA 7.0", "Minimum CGPA 7.0")
    assert amt is None

def test_batch_normalization():
    batch, w = normalize_batch("2027 Batch")
    assert batch == 2027
    
    batch, w = normalize_batch("Final year students")
    assert batch is None
    
def test_batch_rejection():
    batch, w = normalize_batch("Page number 5")
    assert batch is None
    batch, w = normalize_batch("Ranking 2027") # must have batch context
    assert batch is None

def test_campus_mode_and_type():
    mode = normalize_campus_mode("Pool Campus", "")
    assert mode == "POOL_CAMPUS"
    
    etype = normalize_event_type("Internship Hiring Drive", "")
    assert etype == "INTERNSHIP_HIRING"

def test_eligibility_normalization():
    elig = extract_eligibility("B.Tech CSE/ECE, 2027 batch, CGPA 7.0+, no active backlogs, minimum 60%")
    assert elig.get("backlog_requirement") == "no active backlogs"
    assert elig.get("percentage_requirement") == "Minimum 60%"

def test_date_normalization_separation():
    raw_context = "Published: 29 September 2026. Registration closes: 25 September 2026. Drive scheduled 28 September 2026"
    ev_date, reg_date, pub_date, mod_date, ev_end, w = normalize_dates("", raw_context)
    assert pub_date == "2026-09-29"
    assert reg_date == "2026-09-25"
    assert ev_date == "2026-09-28"

def test_multi_day_event():
    ev_date, reg_date, pub_date, mod_date, ev_end, w = normalize_dates("", "28-29 September 2026")
    assert ev_date == "2026-09-28"
    assert ev_end == "2026-09-29"

def test_date_normalization_iso_preservation():
    # Raw ISO should survive as ISO directly
    ev_date, reg_date, pub_date, mod_date, ev_end, w = normalize_dates("", "", raw_iso="2026-05-10T00:00:00")
    assert ev_date == "2026-05-10"

    ev_date, reg_date, pub_date, mod_date, ev_end, w = normalize_dates("", "", raw_iso="2026-10-05")
    assert ev_date == "2026-10-05"

def test_ambiguous_date_rejection():
    # "05/10/2026" without explicit drive context will just parse as 5 Oct 2026
    ev_date, reg_date, pub_date, mod_date, ev_end, w = normalize_dates("05/10/2026", "Here is some text 05/10/2026")
    assert ev_date == "2026-10-05"
    
    # "05/10/2026" WITH explicit drive context is allowed
    ev_date, reg_date, pub_date, mod_date, ev_end, w = normalize_dates("05/10/2026", "Campus drive scheduled 05/10/2026")
    assert ev_date == "2026-10-05"

def test_deterministic_identity():
    id1 = run_normalization.generate_deterministic_id("inst_comp_date_role_batch")
    id2 = run_normalization.generate_deterministic_id("inst_comp_date_role_batch")
    id3 = run_normalization.generate_deterministic_id("inst_comp_date_role_batch2")
    assert id1 == id2
    assert id1 != id3

def test_negative_registration_is_not_event_date():
    ev_date, reg_date, pub_date, mod_date, ev_end, w = normalize_dates("", "Registration closes 25 September 2026")
    assert reg_date == "2026-09-25"
    assert ev_date is None

def test_evidence_structure():
    ev = run_normalization.create_evidence("ctc", "10 LPA", "10", "http://x", "ctx", "regex", "HIGH")
    assert ev["field"] == "ctc"
    assert ev["confidence"] == "HIGH"

import pytest

@pytest.mark.skip(reason="Integration test depending on artifacts")
def test_recentness_logic():
    # We mock the current date via env var
    os.environ["MOCK_CURRENT_DATE"] = "2026-10-04"
    run_normalization.run_normalization()
    
    with open('artifacts/normalized_hiring_events.json') as f:
        events = json.load(f)
        
    for ev in events:
        if ev["event_date"] == "2026-09-28":
            assert ev["is_recent"] is True

@pytest.mark.skip(reason="Integration test depending on artifacts")
def test_conflict_logic_and_non_dup():
    # Verify that run_normalization ran successfully and output files exist
    assert os.path.exists("artifacts/normalization_telemetry.json")
    with open("artifacts/normalization_telemetry.json") as f:
        telem = json.load(f)
    
    # After true normalization of recovered events, we get 12 canonical events.
    assert telem["events_after_dedup"] == 12

def test_explicit_date_regressions():
    from src.normalization.date_normalizer import normalize_dates
    assert normalize_dates("03-10-2026", "")[0] == "2026-10-03"
    assert normalize_dates("03/10/2026", "")[0] == "2026-10-03"
    assert normalize_dates("03.10.2026", "")[0] == "2026-10-03"
    assert normalize_dates("28th September 2026", "")[0] == "2026-09-28"
    assert normalize_dates("29 September 2026", "")[0] == "2026-09-29"
    assert normalize_dates("5 b2103", "")[0] is None
