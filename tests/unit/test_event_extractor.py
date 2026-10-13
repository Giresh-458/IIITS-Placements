import pytest
from src.extraction.event_extractor import extract_from_text

def test_company_article_heading():
    res = extract_from_text("Campus Recruitment Drive by Emicon Advisory Services LLP for B.Tech", "http://x")
    assert res["company_candidate"] == "Emicon Advisory Services LLP"

def test_company_label_value():
    res = extract_from_text("Company Name: Example Technologies\nJob Title: Software Engineer", "http://x")
    assert res["company_candidate"] == "Example Technologies"

def test_job_title_label():
    res = extract_from_text("Company Name: Example Technologies\nJob Title: Software Engineer", "http://x")
    assert res["role_candidate"] == "Software Engineer"

def test_table_row_extraction():
    # Simulated flattened table row
    res = extract_from_text("Company & Name | DH Bars & Wires Private Limited", "http://x")
    assert res["company_candidate"] == "DH Bars & Wires Private Limited"

def test_generic_table_header_rejection():
    # Ensure a header isn't matched
    res = extract_from_text("Company Name | Profile | Eligibility", "http://x")
    assert res["company_candidate"] is None

def test_company_profile_header_distinction():
    # Must distinguish between "Profile: Dev" and "Profile" header
    res = extract_from_text("Job Profile: Java Developer", "http://x")
    assert res["role_candidate"] == "Java Developer"
    
    res = extract_from_text("Profile", "http://x")
    assert res["role_candidate"] is None

def test_branch_label_value():
    res = extract_from_text("Eligible Branches: CSE/ECE", "http://x")
    assert res["branch_candidate"] == "CSE/ECE"

def test_batch_extraction():
    res = extract_from_text("2027 passing out batch", "http://x")
    assert res["batch_candidate"] == "2027 batch"

def test_ctc_extraction():
    res = extract_from_text("Annual Package: 10.5 LPA", "http://x")
    assert res["ctc_candidate"] == "10.5 LPA"
    
def test_stipend_only_extraction():
    res = extract_from_text("Stipend 20,000/month", "http://x")
    assert res["ctc_candidate"] == "20,000/month"

def test_cgpa_extraction():
    res = extract_from_text("Minimum CGPA: 7.0", "http://x")
    assert res["cgpa_candidate"] == "7.0"

def test_registration_deadline_vs_event_date():
    # Only registration is passed to extractor natively here
    res = extract_from_text("Register Before 06.10.26. Drive Date: 10.10.26", "http://x")
    assert res["registration_deadline_candidate"] == "06.10.26"

def test_campus_mode_extraction():
    res = extract_from_text("Physical Campus Drive by Example", "http://x")
    assert res["campus_mode_candidate"] == "ON_CAMPUS"


def test_generic_online_navigation_text_does_not_set_campus_mode():
    res = extract_from_text(
        "ONLINE FEE PAYMENT\nCampus Recruitment Drive by Example",
        "https://example.edu/event",
    )
    assert res["campus_mode_candidate"] is None


def test_explicit_virtual_campus_drive_sets_virtual_mode():
    res = extract_from_text(
        "Virtual Campus Drive by Example",
        "https://example.edu/event",
    )
    assert res["campus_mode_candidate"] == "VIRTUAL"


def test_drive_mode_label_can_set_virtual_mode():
    res = extract_from_text(
        "Company: Example\nMode of Drive: Online\nCampus Recruitment Drive",
        "https://example.edu/event",
    )
    assert res["campus_mode_candidate"] == "VIRTUAL"


def test_generic_online_test_does_not_set_virtual_campus_mode():
    res = extract_from_text(
        "Campus Recruitment Drive by Example. Online aptitude test on 12 October.",
        "https://example.edu/event",
    )
    assert res["campus_mode_candidate"] is None

