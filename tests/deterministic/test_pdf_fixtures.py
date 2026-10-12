import pytest
import os
import pypdf
from src.extraction.event_extractor import extract_event_candidate
from src.orchestration.normalization_adapter import normalize_candidates

def extract_pdf_text(filepath):
    reader = pypdf.PdfReader(filepath)
    return " ".join([page.extract_text() for page in reader.pages])

def test_pdf_normal():
    filepath = os.path.join(os.path.dirname(__file__), '../fixtures/placement/pdf/event_normal.pdf')
    text = extract_pdf_text(filepath)
    
    # URL doesn't matter for pure text extraction as much if it has no keywords, but we'll provide one
    url = "http://localhost/event.pdf"
    
    ev = extract_event_candidate("", text, url, {'institution': 'PDFInst', 'seed_url': url})
    assert ev is not None
    
    norm = normalize_candidates([ev])[0]
    assert norm.company_name == "TechCorp Solutions"
    assert norm.ctc == 12.0
    assert norm.role == "SOFTWARE_ENGINEERING"
    assert "CSE" in norm.eligible_branches
    
def test_pdf_multipage():
    filepath = os.path.join(os.path.dirname(__file__), '../fixtures/placement/pdf/event_multipage.pdf')
    text = extract_pdf_text(filepath)
    
    ev = extract_event_candidate("", text, "http://localhost/event.pdf", {'institution': 'PDFInst', 'seed_url': "http://localhost/event.pdf"})
    assert ev is not None
    
    norm = normalize_candidates([ev])[0]
    assert norm.company_name == "GlobalTech Services"
    assert norm.ctc == 15.0

def test_pdf_table():
    filepath = os.path.join(os.path.dirname(__file__), '../fixtures/placement/pdf/event_table.pdf')
    text = extract_pdf_text(filepath)
    
    # PDF tables usually extract as lines of text
    ev = extract_event_candidate("", text, "http://localhost/event.pdf", {'institution': 'PDFInst', 'seed_url': "http://localhost/event.pdf"})
    assert ev is not None
    
    norm = normalize_candidates([ev])[0]
    assert norm.ctc == 10.0
