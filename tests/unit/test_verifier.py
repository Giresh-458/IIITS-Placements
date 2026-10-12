import pytest
import httpx
from src.models.domain import SourceCapabilities, SourceAccessClassification, SourceNode
from scripts.verify_sources import is_authentication_wall, extract_capabilities, assign_category, parse_date_with_context, is_recent
from src.models.enums import SourceCategory
from datetime import datetime

class MockResponse:
    def __init__(self, url, status_code):
        self.url = url
        self.status_code = status_code

def test_date_parsing_with_context():
    d, conf = parse_date_with_context("28th September", "Posted on 1 Oct 2026")
    assert d.year == 2026
    assert d.month == 9
    assert d.day == 28
    assert conf == "MEDIUM"

    d, conf = parse_date_with_context("25th september", "2026-09-20")
    assert d.year == 2026
    assert d.month == 9
    assert d.day == 25
    assert conf == "MEDIUM"

    d, conf = parse_date_with_context("29 September 2026", "")
    assert d.year == 2026
    assert d.month == 9
    assert d.day == 29
    assert conf == "HIGH"

    d, conf = parse_date_with_context("1st October 2026", "")
    assert d.year == 2026
    assert d.month == 10
    assert d.day == 1
    assert conf == "HIGH"

    d, conf = parse_date_with_context("28 September", "")
    assert d.year == 2026 # Fallback to crawl year
    assert d.month == 9
    assert d.day == 28
    assert conf == "LOW"

def test_recent_date_logic():
    assert is_recent(datetime(2026, 9, 28)) == True
    assert is_recent(datetime(2026, 9, 19)) == False
    assert is_recent(datetime(2026, 10, 4)) == True
    assert is_recent(datetime(2026, 10, 5)) == False

def test_login_keyword_not_authenticated():
    text = "Students must login to the portal. This is a public placement page."
    html = "<html><body>" + text + "</body></html>"
    resp = MockResponse("http://example.com/placement", 200)
    assert not is_authentication_wall(resp, text, html)

def test_login_redirect_is_authenticated():
    text = "Please Login"
    html = '<html><body><input type="password"/></body></html>'
    resp = MockResponse("http://example.com/login", 200)
    assert is_authentication_wall(resp, text, html)

def test_403_is_not_authenticated():
    text = "Access denied"
    html = "<html><body>" + text + "</body></html>"
    resp = MockResponse("http://example.com/placement", 403)
    assert not is_authentication_wall(resp, text, html)

def test_college_vs_company_contact():
    text_college = "Placement Officer: 9876543210"
    html_col = "<html><body>" + text_college + "</body></html>"
    caps_col = extract_capabilities(html_col, text_college, "http://example.com")
    assert caps_col.has_contact_phone.value == "UNKNOWN"

    text_comp = "HR Contact:\nJane Doe\n+91 9876543211\n"
    html_comp = "<html><body><pre>" + text_comp + "</pre></body></html>"
    caps_comp = extract_capabilities(html_comp, text_comp, "http://example.com")
    assert caps_comp.has_contact_phone.value == "TRUE"
    assert caps_comp.has_contact_name.value == "TRUE"

def test_procedure_language_not_event():
    cases = [
        "Companies can register for campus recruitment.",
        "Job Announcement Form will be available in the portal.",
        "Recruitment procedure for companies.",
        "Past recruiters include Google, Microsoft...",
        "Placement policy.",
        "Contact the TPO for placements.",
        "JAF will be visible after login."
    ]
    for text in cases:
        html = f"<html><body>{text}</body></html>"
        caps = extract_capabilities(html, text, "http://example.com")
        assert caps.event_discovery.value == "UNKNOWN", f"Failed on: {text}"

def test_generic_event_title_not_event_discovery():
    text = "31 Jul 2026 — Internship Hiring Drive"
    html = f"<html><body>{text}</body></html>"
    caps = extract_capabilities(html, text, "http://example.com")
    assert caps.event_discovery.value == "UNKNOWN"

def test_valid_event_evidence():
    cases = [
        "Campus Recruitment Drive. Company: TechCorp. Drive Date: 12-10-2026",
        "Campus Recruitment Drive. Company: TechCorp. Batch: 2027. Registration Deadline: 12-10-2026",
        "Physical Campus Drive. Company: TechCorp. Drive Date: 12-10-2026"
    ]
    for text in cases:
        html = f"<html><body>{text}</body></html>"
        caps = extract_capabilities(html, text, "http://example.com")
        assert caps.event_discovery.value == "TRUE", f"Failed on: {text}"

def test_public_event_index_categorization():
    node = SourceNode(source_id="1", url="http://example.com/events")
    node.page_type = "EVENT_INDEX"
    caps = SourceCapabilities()
    cat = assign_category(node, caps, [], [], "<html><body>Some events</body></html>")
    assert cat == SourceCategory.P1_PUBLIC_EVENT_INDEX

def test_public_notice_index_categorization():
    node = SourceNode(source_id="1", url="http://example.com/notice-board")
    node.page_type = "NOTICE_INDEX"
    caps = SourceCapabilities()
    # No concrete event found on root or children
    cat = assign_category(node, caps, [], [], "<html><body>Notice Board</body></html>")
    assert cat == SourceCategory.P1_PUBLIC_NOTICE_INDEX

def test_historical_company_list_categorization():
    node = SourceNode(source_id="1", url="http://example.com/recruiters")
    node.page_type = "UNKNOWN"
    caps = SourceCapabilities()
    html = "<html><body>Past recruiters include TechCorp, Google.</body></html>"
    cat = assign_category(node, caps, [], [], html)
    assert cat == SourceCategory.P1_COMPANY_HISTORY
