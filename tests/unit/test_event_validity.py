import pytest
from src.normalization.event_validator import validate_event_candidate

def test_on_campus_failure_is_rejected():
    state = validate_event_candidate(
        comp_norm=None,
        role_fam="UNKNOWN",
        ctc_amt=None,
        reg_date=None,
        ev_date=None,
        batch_norm=None,
        campus_mode="ON_CAMPUS",
        raw_event_text="Campus placement details"
    )
    assert state == "REJECTED_NON_EVENT"

def test_valid_incomplete_event_preserved():
    # Only Date, but has REGISTRATION deadline and Context (strong hiring event indicator)
    state = validate_event_candidate(
        comp_norm=None,
        role_fam="UNKNOWN",
        ctc_amt=None,
        reg_date="2026-09-28",
        ev_date="2026-09-29",
        batch_norm=None,
        campus_mode="VIRTUAL",
        raw_event_text="Virtual Recruitment Drive on 29th Sept. Register by 28th."
    )
    assert state == "VALID_INCOMPLETE_EVENT"
    
def test_valid_complete_event():
    # Adding recruitment context to ensure it passes the new strict rule
    state = validate_event_candidate(
        comp_norm="Contenterra",
        role_fam="SOFTWARE_ENGINEERING",
        ctc_amt=None,
        reg_date=None,
        ev_date="2026-09-29",
        batch_norm=2026,
        campus_mode="ON_CAMPUS",
        raw_event_text="Campus placement for Contenterra"
    )
    assert state == "VALID_COMPLETE_EVENT"

# 3. Add adversarial negative tests
def test_negative_regression_company_alone():
    state = validate_event_candidate(comp_norm="Example Corp", role_fam="UNKNOWN", ctc_amt=None, reg_date=None, ev_date=None, batch_norm=None, campus_mode="UNKNOWN", raw_event_text="Welcome to Example Corp")
    assert state == "REJECTED_NON_EVENT"

def test_negative_regression_company_unrelated_date():
    state = validate_event_candidate(comp_norm="Example Corp", role_fam="UNKNOWN", ctc_amt=None, reg_date=None, ev_date="2026-09-01", batch_norm=None, campus_mode="UNKNOWN", raw_event_text="Example Corp established 2026-09-01")
    assert state == "REJECTED_NON_EVENT"

def test_negative_regression_company_batch():
    state = validate_event_candidate(comp_norm="Example Corp", role_fam="UNKNOWN", ctc_amt=None, reg_date=None, ev_date=None, batch_norm=2026, campus_mode="UNKNOWN", raw_event_text="Example Corp 2026")
    assert state == "REJECTED_NON_EVENT"

def test_negative_regression_company_role():
    state = validate_event_candidate(comp_norm="Example Corp", role_fam="SOFTWARE_ENGINEERING", ctc_amt=None, reg_date=None, ev_date=None, batch_norm=None, campus_mode="UNKNOWN", raw_event_text="Example Corp Software Engineer")
    assert state == "REJECTED_NON_EVENT"

def test_negative_regression_company_ctc():
    state = validate_event_candidate(comp_norm="Example Corp", role_fam="UNKNOWN", ctc_amt=10.0, reg_date=None, ev_date=None, batch_norm=None, campus_mode="UNKNOWN", raw_event_text="Example Corp 10 LPA")
    assert state == "REJECTED_NON_EVENT"

def test_negative_regression_company_generic_page():
    state = validate_event_candidate(comp_norm="Example Corp", role_fam="UNKNOWN", ctc_amt=None, reg_date=None, ev_date=None, batch_norm=None, campus_mode="UNKNOWN", raw_event_text="We do recruitment for students")
    assert state == "REJECTED_NON_EVENT"

def test_negative_regression_ctc_reg_deadline_no_context():
    state = validate_event_candidate(comp_norm=None, role_fam="UNKNOWN", ctc_amt=10.0, reg_date="2026-09-01", ev_date=None, batch_norm=None, campus_mode="UNKNOWN", raw_event_text="CTC 10 LPA Registration deadline 2026-09-01")
    assert state == "REJECTED_NON_EVENT"

def test_negative_regression_role_recruitment_wording_no_employer():
    # Only 1 structured field (role) and context. Not enough.
    state = validate_event_candidate(comp_norm=None, role_fam="SOFTWARE_ENGINEERING", ctc_amt=None, reg_date=None, ev_date=None, batch_norm=None, campus_mode="UNKNOWN", raw_event_text="Hiring Software Engineer")
    assert state == "REJECTED_NON_EVENT"

def test_negative_regression_batch_generic_page():
    state = validate_event_candidate(comp_norm=None, role_fam="UNKNOWN", ctc_amt=None, reg_date=None, ev_date=None, batch_norm=2026, campus_mode="UNKNOWN", raw_event_text="Batch 2026 students")
    assert state == "REJECTED_NON_EVENT"

def test_negative_regression_arbitrary_date_ctc():
    state = validate_event_candidate(comp_norm=None, role_fam="UNKNOWN", ctc_amt=10.0, reg_date=None, ev_date="2026-09-01", batch_norm=None, campus_mode="UNKNOWN", raw_event_text="10 LPA on 2026-09-01")
    assert state == "REJECTED_NON_EVENT"

# 4. Add positive regression tests
def test_positive_regression_employer_campus_recruitment_date():
    state = validate_event_candidate(comp_norm="Tech Corp", role_fam="UNKNOWN", ctc_amt=None, reg_date=None, ev_date="2026-10-01", batch_norm=None, campus_mode="UNKNOWN", raw_event_text="Tech Corp campus recruitment drive on 2026-10-01")
    assert state == "VALID_COMPLETE_EVENT"

def test_positive_regression_employer_schedule_date():
    state = validate_event_candidate(comp_norm="Tech Corp", role_fam="UNKNOWN", ctc_amt=None, reg_date=None, ev_date="2026-10-01", batch_norm=None, campus_mode="UNKNOWN", raw_event_text="Tech Corp schedule: 2026-10-01")
    assert state == "VALID_COMPLETE_EVENT"

def test_positive_regression_placement_notice_evidence():
    # Multiple fields (>= 3) establish context even without explicit keywords
    state = validate_event_candidate(comp_norm="Tech Corp", role_fam="SOFTWARE_ENGINEERING", ctc_amt=12.0, reg_date=None, ev_date=None, batch_norm=None, campus_mode="UNKNOWN", raw_event_text="Tech Corp SDE 12 LPA")
    assert state == "VALID_INCOMPLETE_EVENT"

def test_positive_regression_employer_batch_placement_context():
    state = validate_event_candidate(comp_norm="Tech Corp", role_fam="UNKNOWN", ctc_amt=None, reg_date=None, ev_date=None, batch_norm=2026, campus_mode="UNKNOWN", raw_event_text="Tech Corp placement drive for 2026 batch")
    assert state == "VALID_INCOMPLETE_EVENT"
