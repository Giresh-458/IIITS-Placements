import pytest
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup
from src.evidence.rehydrator import parse_html_to_payload, rehydrate_url

def test_json_ld_parsing():
    html = """
    <html>
        <head>
            <title>Event Page</title>
            <script type="application/ld+json">
                {
                    "@context": "https://schema.org",
                    "@type": "Event",
                    "name": "Software Engineer Recruitment",
                    "startDate": "2026-11-20",
                    "organizer": {
                        "@type": "Organization",
                        "name": "TechCorp Inc."
                    }
                }
            </script>
        </head>
        <body>
            <p>Welcome to our event page.</p>
        </body>
    </html>
    """
    payload = parse_html_to_payload("http://example.com/event", html, "HTML")
    assert payload["method"] == "HTML"
    assert len(payload["json_ld"]) == 1
    assert payload["json_ld"][0]["name"] == "Software Engineer Recruitment"
    assert payload["json_ld"][0]["startDate"] == "2026-11-20"
    assert payload["json_ld"][0]["organizer"]["name"] == "TechCorp Inc."

@patch("src.evidence.rehydrator.httpx.Client.get")
def test_pdf_rehydration(mock_get):
    import io
    from pypdf import PdfWriter
    
    # Create an in-memory PDF
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100) # pypdf blank page doesn't have text
    # Actually, pypdf requires a bit more to add text easily, 
    # so we'll mock the pypdf.PdfReader call to avoid building a valid text PDF in-memory here.

@patch("src.evidence.rehydrator.pypdf.PdfReader")
@patch("src.evidence.rehydrator.httpx.Client.get")
def test_pdf_rehydration_mocked(mock_get, mock_reader):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/pdf"}
    mock_resp.content = b"%PDF-1.4"
    mock_get.return_value = mock_resp
    
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Campus Recruitment Drive by PDFCompany. CTC: 5 LPA. Branch: CSE"
    mock_reader.return_value.pages = [mock_page]
    
    payload, audit = rehydrate_url("http://example.com/doc.pdf")
    assert payload is not None
    assert payload["method"] == "PDF"
    assert len(payload["paragraphs"]) == 1
    assert "PDFCompany" in payload["paragraphs"][0]
    assert audit["pdf"]["succeeded"] == True

@patch("src.evidence.rehydrator.sync_playwright")
@patch("src.evidence.rehydrator.httpx.Client.get")
def test_js_fallback_rehydration(mock_get, mock_playwright):
    # Mock HTTP response to be a short "Loading javascript..." string
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "text/html"}
    mock_resp.text = "<html><body>Loading javascript...</body></html>"
    mock_get.return_value = mock_resp
    
    # Mock Playwright
    mock_p = MagicMock()
    mock_browser = MagicMock()
    mock_page = MagicMock()
    
    mock_playwright.return_value.__enter__.return_value = mock_p
    mock_p.chromium.launch.return_value = mock_browser
    mock_browser.new_page.return_value = mock_page
    
    js_html = "<html><body><h1>Campus Drive by JSCompany</h1><p>Role: SDE</p></body></html>"
    mock_page.content.return_value = js_html
    
    payload, audit = rehydrate_url("http://example.com/js-event")
    
    # HTTP Attempted First (implicit, since mock_get was called)
    assert mock_get.called
    # Playwright Invoked
    assert mock_browser.new_page.called
    assert mock_page.goto.called
    
    assert payload is not None
    assert payload["method"] == "JS"
    assert payload["headings"][0] == "Campus Drive by JSCompany"
    assert payload["paragraphs"][0] == "Role: SDE"
    assert audit["js"]["succeeded"] == True
