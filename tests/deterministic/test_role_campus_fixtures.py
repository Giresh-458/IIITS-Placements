import pytest
from src.models.domain import NormalizedHiringEvent
from src.classification.business_rules import classify_event

def create_event_with_role(role_raw: str, role_family: str = "UNKNOWN") -> NormalizedHiringEvent:
    return NormalizedHiringEvent(
        event_id="test",
        institution="TestInst",
        company_name="Test",
        role_raw=role_raw,
        role_family=role_family
    )

def test_role_taxonomy():
    # Technical
    assert classify_event(create_event_with_role("Backend Engineer")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("Frontend Developer")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("Full Stack Engineer")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("Mobile App Dev")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("GenAI Engineer")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("LLM Researcher")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("RAG Specialist")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("QA Automation Engineer")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("Data Engineer")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("Cloud DevOps Engineer")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("SRE")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("Cybersecurity Analyst")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("Firmware Engineer")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("Embedded Systems")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("IoT Developer")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("Network Engineer")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("VLSI Software")).role_relevance == "TRUE"
    assert classify_event(create_event_with_role("Technical Solutions")).role_relevance == "TRUE"
    
    # Non-technical
    assert classify_event(create_event_with_role("BPO Executive")).role_relevance == "FALSE"
    assert classify_event(create_event_with_role("Sales Manager")).role_relevance == "FALSE"

def test_campus_mode():
    from src.extraction.event_extractor import extract_event_candidate
    from src.orchestration.normalization_adapter import normalize_candidates
    
    html = "On-Campus Recruitment Drive by TechCorp Solutions hiring for SDE\nCTC: 10 LPA"
    ev = extract_event_candidate("", html, "http://localhost/event.html", {'institution': 'I'})
    assert normalize_candidates([ev])[0].campus_mode == "ON_CAMPUS"
    
    html = "Pool Campus Recruitment Drive by TechCorp Solutions hiring for SDE\nCTC: 10 LPA"
    ev = extract_event_candidate("", html, "http://localhost/event.html", {'institution': 'I'})
    assert normalize_candidates([ev])[0].campus_mode == "POOL_CAMPUS"
    
    html = "Virtual Recruitment Drive by TechCorp Solutions hiring for SDE\nCTC: 10 LPA"
    ev = extract_event_candidate("", html, "http://localhost/event.html", {'institution': 'I'})
    assert normalize_candidates([ev])[0].campus_mode == "VIRTUAL"
