import httpx
from bs4 import BeautifulSoup
import json
import io
import pypdf
from playwright.sync_api import sync_playwright

def parse_html_to_payload(url: str, html: str, method: str):
    soup = BeautifulSoup(html, 'html.parser')
    payload = {
        "url": url,
        "method": method,
        "title": soup.title.string if soup.title else "",
        "headings": [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])],
        "paragraphs": [p.get_text(strip=True) for p in soup.find_all('p')],
        "tables": [],
        "lists": [li.get_text(strip=True) for li in soup.find_all('li')],
        "json_ld": [],
        "links": [{"text": a.get_text(strip=True), "href": a.get('href')} for a in soup.find_all('a', href=True)]
    }
    
    # Parse Tables into Label | Value format
    for table in soup.find_all('table'):
        parsed_table = []
        for row in table.find_all('tr'):
            cells = row.find_all(['th', 'td'])
            if len(cells) == 2:
                label = cells[0].get_text(separator=" ", strip=True)
                value = cells[1].get_text(separator=" ", strip=True)
                parsed_table.append(f"{label} | {value}")
            elif len(cells) > 0:
                parsed_table.append(" | ".join([c.get_text(separator=" ", strip=True) for c in cells]))
        payload["tables"].extend(parsed_table)
        
    # Parse JSON-LD
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            payload["json_ld"].append(json.loads(script.string))
        except:
            pass
            
    return payload

def rehydrate_url(url: str):
    audit = {
        "html": {"attempted": False, "succeeded": False},
        "pdf": {"attempted": False, "succeeded": False},
        "js": {"attempted": False, "succeeded": False},
        "api": {"attempted": False, "succeeded": False},
        "table": {"attempted": False, "succeeded": False},
        "json_ld": {"attempted": False, "succeeded": False},
        "status_code": None,
        "error": None
    }
    
    if not url:
        audit["error"] = "No URL provided"
        return None, audit
        
    try:
        transport = httpx.HTTPTransport(verify=False)
        with httpx.Client(transport=transport, headers={"User-Agent": "Mozilla/5.0"}) as client:
            audit["html"]["attempted"] = True
            resp = client.get(url, timeout=15.0, follow_redirects=True)
            audit["status_code"] = resp.status_code
            
            if resp.status_code != 200:
                audit["error"] = f"HTTP {resp.status_code}"
                return None, audit
                
            content_type = resp.headers.get('content-type', '').lower()
            
            # PDF Path
            if 'application/pdf' in content_type or url.lower().endswith('.pdf'):
                audit["pdf"]["attempted"] = True
                reader = pypdf.PdfReader(io.BytesIO(resp.content))
                text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
                audit["pdf"]["succeeded"] = True
                return {
                    "url": url,
                    "method": "PDF",
                    "paragraphs": text.split('\n'),
                    "headings": [],
                    "tables": [],
                    "lists": [],
                    "json_ld": []
                }, audit
                
            # HTML Path
            audit["html"]["succeeded"] = True
            html = resp.text
            text_len = len(BeautifulSoup(html, 'html.parser').get_text(strip=True))
            
            # JS Path
            if text_len < 2000 and ("loading" in html.lower() or "javascript" in html.lower()):
                audit["js"]["attempted"] = True
                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch()
                        page = browser.new_page()
                        page.goto(url, wait_until="networkidle", timeout=15000)
                        js_html = page.content()
                        browser.close()
                        audit["js"]["succeeded"] = True
                        payload = parse_html_to_payload(url, js_html, "JS")
                except Exception as e:
                    audit["error"] = f"JS Playwright failed: {str(e)}"
                    payload = parse_html_to_payload(url, html, "HTML") # fallback
            else:
                payload = parse_html_to_payload(url, html, "HTML")
                
            if len(payload["tables"]) > 0:
                audit["table"]["attempted"] = True
                audit["table"]["succeeded"] = True
            if len(payload["json_ld"]) > 0:
                audit["json_ld"]["attempted"] = True
                audit["json_ld"]["succeeded"] = True
                
            return payload, audit
    except Exception as e:
        audit["error"] = str(e)
        return None, audit
