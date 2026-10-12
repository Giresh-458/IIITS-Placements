import asyncio
import json
import httpx
from playwright.async_api import async_playwright
from datetime import datetime
import re
import os
import uuid
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urlunparse
from typing import Dict, List, Tuple, Set, Optional

from src.models.domain import (
    SourceVerificationEvidence, SourceCapabilities, SourceAccessClassification,
    SourceQualityScore, CapabilityEvidence, SourceNode
)
from src.models.enums import SourceCategory

URLS = [
    ("RGUKT Basar", "https://hub.rgukt.ac.in/hub/tnp/index/0", "EVENT_DISCOVERY"),
    ("Trident Academy of Technology", "https://trident.ac.in/placementnotice/", "EVENT_DISCOVERY"),
    ("GIET", "https://giet.edu.in/event/", "EVENT_DISCOVERY"),
    ("GIET Archive", "https://giet.edu.in/placement-notice/", "EVENT_DISCOVERY"),
    ("AAA College of Engineering & Technology", "https://aaaenggcoll.ac.in/placement/", "EVENT_DISCOVERY"),
    ("KIT Tiptur", "https://kittiptur.ac.in/placements", "EVENT_DISCOVERY"),
    ("IIT Bombay", "https://campus.placements.iitb.ac.in/", "VALIDATION"),
    ("IIT Kanpur", "https://spo.iitk.ac.in/companies", "COMPANY_HISTORY"),
    ("IIT Kanpur Placement", "https://placement.iitk.ac.in/", "VALIDATION"),
    ("IIT Delhi", "https://ocs.iitd.ac.in/", "EVENT_DISCOVERY"),
    ("IIT Delhi Events", "https://ocs.iitd.ac.in/events", "EVENT_DISCOVERY"),
    ("IIT (BHU) Varanasi", "https://placement.iitbhu.ac.in/forum/c/notice-board/", "NOTICE_BOARD"),
    ("NITK Surathkal", "https://iris.nitk.ac.in/hrms/placement", "RECRUITER_INTELLIGENCE"),
    ("IIIT Sri City", "https://iiits.ac.in/campus-placement/", "TARGET_PROFILE"),
    ("IIIT Sri City Archive", "https://iiits.ac.in/campus-placement-archive/", "TARGET_PROFILE")
]

MAX_SOURCE_DEPTH = 2
MAX_CHILD_PAGES = 5
MAX_PAGES_PER_SOURCE = 15
RECENT_WINDOW_START = datetime(2026, 9, 20)
RECENT_WINDOW_END = datetime(2026, 10, 4)

def parse_date_with_context(date_str: str, html_context: str = "") -> Tuple[Optional[datetime], str]:
    if not date_str:
        return None, "UNKNOWN"
        
    # Check if year is explicit in the string
    has_explicit_year = bool(re.search(r'\b(202[0-9])\b', date_str))
    
    # Try to extract context year
    context_year = None
    if html_context:
        pub_match = re.search(r'\b(202[0-9])\b', html_context)
        if pub_match:
            context_year = pub_match.group(1)
            
    # Normalize string
    clean_str = re.sub(r'(st|nd|rd|th)\b', '', date_str, flags=re.IGNORECASE).strip()
    
    try:
        from dateutil import parser
        # Parse without a default year first to see if it infers current year automatically
        dt = parser.parse(clean_str, fuzzy=True, default=datetime(1900, 1, 1))
        
        confidence = "UNKNOWN"
        final_year = dt.year
        
        if final_year != 1900:
            confidence = "HIGH"
        elif has_explicit_year:
            final_year = dt.year # Should be handled by parser if explicit
            confidence = "HIGH"
        elif context_year:
            final_year = int(context_year)
            confidence = "MEDIUM"
        else:
            # Fallback to crawl year if month/day is unambiguous
            final_year = 2026
            confidence = "LOW"
            
        return dt.replace(year=final_year), confidence
        
    except:
        return None, "UNKNOWN"

def is_recent(d: datetime) -> bool:
    if not d: return False
    return RECENT_WINDOW_START.date() <= d.date() <= RECENT_WINDOW_END.date()

def clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup(["script", "style"]):
        script.extract()
    return soup.get_text(separator="\n", strip=True)

def is_authentication_wall(resp: httpx.Response, text: str, html: str) -> bool:
    if resp.status_code == 401:
        return True
    parsed = urlparse(str(resp.url))
    if any(p in parsed.path.lower() for p in ['/login', '/signin', '/auth']):
        if len(text) < 2000:
            return True
    soup = BeautifulSoup(html, "html.parser")
    password_inputs = soup.find_all("input", type="password")
    if password_inputs and len(text) < 3000:
        return True
    return False

def extract_capabilities(html: str, text: str, source_url: str) -> SourceCapabilities:
    caps = SourceCapabilities()
    
    strong_context = re.search(
        r'\b(campus recruitment drive|on-campus recruitment|physical campus drive|virtual campus drive|pooled campus recruitment|campus hiring|recruitment notice|placement drive|company hiring students)\b',
        text, re.IGNORECASE
    )
    
    concrete_found = False
    
    company_match = re.search(r'\b(Company|Recruiter|Organization)\s*[:\-]?\s*([A-Za-z0-9\&\s\.]{3,50})\b', text, re.IGNORECASE)
    if company_match:
        caps.has_company.value = "TRUE"
        caps.has_company.evidence_text = company_match.group(0)[:50]
        caps.event_discovery.company_name_if_available = company_match.group(2)[:50]
        concrete_found = True
        
    role_match = re.search(r'\b(Role|Profile|Designation|Job Title)\s*[:\-]?\s*([A-Za-z\s]{3,50})\b', text, re.IGNORECASE)
    if role_match:
        caps.has_role.value = "TRUE"
        caps.has_role.evidence_text = role_match.group(0)[:50]
        caps.event_discovery.role_if_available = role_match.group(2)[:50]
        concrete_found = True
        
    ctc_match = re.search(r'\b(CTC|Salary|Package)\s*[:\-]?\s*([\d\.]+\s*(LPA|lakhs?|K|k))\b', text, re.IGNORECASE)
    if ctc_match:
        caps.has_ctc.value = "TRUE"
        caps.has_ctc.evidence_text = ctc_match.group(0)[:50]
        caps.event_discovery.ctc_if_available = ctc_match.group(2)[:50]
        concrete_found = True
        
    date_match = re.search(r'\b(Drive Date|Date of Drive|Interview Date|Schedule|Date|Campus Drive|On)\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}([-/]\d{2,4})?|\d{1,2}(st|nd|rd|th)?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*(?:\s+\d{4})?)\b', text, re.IGNORECASE)
    if date_match:
        caps.has_event_date.value = "TRUE"
        caps.has_event_date.evidence_text = date_match.group(0)[:80]
        caps.event_discovery.event_date_if_available = date_match.group(2)[:50]
        concrete_found = True
        
    reg_match = re.search(r'\b(Registration Deadline|Apply Before|Last Date)\b.{0,40}\b(\d{1,2}[-/]\d{1,2}([-/]\d{2,4})?|\d{1,2}(st|nd|rd|th)?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*(?:\s+\d{4})?)\b', text, re.IGNORECASE)
    if reg_match:
        caps.has_registration_deadline.value = "TRUE"
        caps.has_registration_deadline.evidence_text = reg_match.group(0)[:80]
        caps.event_discovery.registration_deadline_if_available = reg_match.group(2)[:50]
        concrete_found = True
        
    branch_match = re.search(r'\b(Eligible Branches|Branches Allowed|Branches|Eligibility)\s*[:\-]?\s*([A-Za-z,\s]{3,50})\b', text, re.IGNORECASE)
    if branch_match:
        caps.has_eligible_branches.value = "TRUE"
        caps.has_eligible_branches.evidence_text = branch_match.group(0)[:50]
        caps.event_discovery.branch_if_available = branch_match.group(2)[:50]
        concrete_found = True
        
    batch_match = re.search(r'\b(Batch|Year of Passing|YOP)\s*[:\-]?\s*(202[3-7])\b', text, re.IGNORECASE)
    if batch_match:
        caps.has_batch.value = "TRUE"
        caps.has_batch.evidence_text = batch_match.group(0)[:50]
        caps.event_discovery.batch_if_available = batch_match.group(2)[:50]
        concrete_found = True

    if strong_context and concrete_found:
        caps.event_discovery.value = "TRUE"
        caps.event_discovery.evidence_text = strong_context.group(0)
        caps.event_discovery.source_url = source_url
        caps.event_discovery.evidence_excerpt = text[max(0, strong_context.start()-50):min(len(text), strong_context.end()+150)].replace('\n', ' ')
        
    for match in re.finditer(r'(\+91[-\s]?\d{10}|\b\d{10}\b|[\w\.]+@[\w\.]+)', text):
        start = max(0, match.start() - 100)
        end = min(len(text), match.end() + 100)
        context = text[start:end].replace('\n', ' ')
        if re.search(r'\b(HR|Talent Acquisition|Recruiter|Contact Person|Recruitment Team)\b', context, re.IGNORECASE):
            if "@" in match.group(0):
                caps.has_contact_email.value = "TRUE"
            else:
                caps.has_contact_phone.value = "TRUE"
            caps.has_contact_name.value = "TRUE"
            caps.has_contact_name.evidence_text = context[:100]
        elif re.search(r'\b(Training and Placement Officer|TPO|Placement Cell|Coordinator)\b', context, re.IGNORECASE):
            pass

    return caps

def score_link(href: str, text: str) -> int:
    score = 0
    t = (href + " " + text).lower()
    if re.search(r'(notice|drive|recruitment|circular|campus-drive)', t):
        score += 50
    if re.search(r'(event|hiring|career)', t):
        score += 30
    if re.search(r'(page|p=)', t):
        score += 20
    if re.search(r'(archive)', t):
        score += 10
    if re.search(r'(policy|procedure|contact|about|infrastructure)', t):
        score -= 20
    return score

def get_page_type(url: str, text: str) -> str:
    url_l = url.lower()
    text_l = text.lower()
    if re.search(r'(page|p=)', url_l):
        return "ARCHIVE"
    if re.search(r'(notice-board|forum)', url_l):
        return "NOTICE_INDEX"
    if re.search(r'(notice)', url_l):
        return "NOTICE_RECORD"
    if re.search(r'(circular)', url_l):
        return "CIRCULAR"
    if re.search(r'(drive|hiring)', url_l):
        return "EVENT_RECORD"
    if re.search(r'(events|placements|placement-notice)', url_l):
        return "EVENT_INDEX"
    if re.search(r'(procedure|policy)', url_l):
        return "PROCEDURE"
    return "UNKNOWN"

def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ''))

async def fetch_and_extract(client, url: str, browser) -> Tuple[SourceNode, SourceCapabilities, str]:
    node = SourceNode(source_id=str(uuid.uuid4()), url=url)
    caps = SourceCapabilities()
    html = ""
    try:
        resp = await client.get(url)
        node.http_status = resp.status_code
        node.redirect_chain = [str(r.url) for r in resp.history]
        node.url = str(resp.url)
        
        if resp.status_code == 403:
            node.access_status = SourceAccessClassification.BLOCKED_OR_FORBIDDEN
            return node, caps, html
            
        html = resp.text
        text = clean_text(html)
        is_auth = is_authentication_wall(resp, text, html)
        node.is_auth_wall = is_auth
        
        if len(text) < 2000 and not is_auth:
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=20000, wait_until="networkidle")
                html = await page.content()
                text = clean_text(html)
                is_auth = is_authentication_wall(resp, text, html)
                node.is_auth_wall = is_auth
                node.access_status = SourceAccessClassification.PUBLIC_JS
            except Exception:
                pass
            finally:
                await page.close()
        else:
            node.access_status = SourceAccessClassification.PUBLIC_STATIC_HTML
            
        if is_auth:
            node.access_status = SourceAccessClassification.AUTHENTICATED_PORTAL
            
        node.page_type = get_page_type(url, text[:1000])
        caps = extract_capabilities(html, text, url)
        
    except Exception as e:
        node.http_status = 0
        node.access_status = SourceAccessClassification.NOT_REACHABLE
        
    return node, caps, html

def assign_category(seed_node: SourceNode, seed_caps: SourceCapabilities, child_nodes: List[SourceNode], child_caps: List[SourceCapabilities], html: str) -> SourceCategory:
    if seed_node.access_status == SourceAccessClassification.BLOCKED_OR_FORBIDDEN:
        return SourceCategory.BLOCKED_OR_FORBIDDEN
    if seed_node.access_status == SourceAccessClassification.AUTHENTICATED_PORTAL:
        return SourceCategory.AUTHENTICATED_PORTAL
    if seed_node.access_status == SourceAccessClassification.NOT_REACHABLE:
        return SourceCategory.NOT_REACHABLE
        
    text_l = clean_text(html).lower()
    
    # 1. Did we find concrete event details on root?
    if seed_caps.event_discovery.value == "TRUE":
        return SourceCategory.P0_DIRECT_EVENT_FEED
        
    # 2. Did we find concrete event details on children?
    for c_node, c_cap in zip(child_nodes, child_caps):
        if c_cap.event_discovery.value == "TRUE":
            if seed_node.page_type == "ARCHIVE" or "archive" in seed_node.url:
                return SourceCategory.P0_PUBLIC_EVENT_ARCHIVE
            return SourceCategory.P0_EVENT_INDEX_WITH_CHILD_DETAILS
            
    # 3. No concrete events found. Is it an index?
    if seed_node.page_type == "NOTICE_INDEX" or re.search(r'\b(notice board|circulars|notices)\b', text_l):
        return SourceCategory.P1_PUBLIC_NOTICE_INDEX
        
    if seed_node.page_type == "EVENT_INDEX" or re.search(r'\b(campus recruitment drives|hiring events|event schedule|internship hiring drive)\b', text_l):
        return SourceCategory.P1_PUBLIC_EVENT_INDEX
        
    if seed_caps.has_contact_phone.value == "TRUE" or seed_caps.has_contact_email.value == "TRUE":
        return SourceCategory.P1_PUBLIC_RECRUITER_CONTACT
        
    if re.search(r'\b(past recruiters|our recruiters|placement statistics|company history)\b', text_l):
        return SourceCategory.P1_COMPANY_HISTORY
        
    return SourceCategory.P1_PUBLIC_VALIDATION

async def verify_source_tree(inst: str, seed_url: str, browser) -> Dict:
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
        seed_node, seed_caps, seed_html = await fetch_and_extract(client, seed_url, browser)
        if seed_node.page_type == "UNKNOWN":
            seed_node.page_type = "ROOT"
        
        nodes = [seed_node]
        child_caps_list = []
        child_nodes = []
        
        if seed_node.access_status in [SourceAccessClassification.PUBLIC_STATIC_HTML, SourceAccessClassification.PUBLIC_JS]:
            soup = BeautifulSoup(seed_html, "html.parser")
            base_url = seed_node.url
            domain = urlparse(base_url).netloc
            links_scored = []
            seen = set([normalize_url(base_url)])
            
            for a in soup.find_all('a', href=True):
                href = a['href']
                full_url = urljoin(base_url, href)
                norm_url = normalize_url(full_url)
                if urlparse(norm_url).netloc == domain and norm_url not in seen:
                    score = score_link(href, a.get_text())
                    if score > 0:
                        links_scored.append((score, norm_url))
                        seen.add(norm_url)
                        
            links_scored.sort(key=lambda x: x[0], reverse=True)
            top_links = [url for score, url in links_scored[:MAX_CHILD_PAGES]]
            
            for child_url in top_links:
                child_node, child_caps, _ = await fetch_and_extract(client, child_url, browser)
                child_node.parent_source_id = seed_node.source_id
                child_node.depth = 1
                nodes.append(child_node)
                child_caps_list.append(child_caps)
                child_nodes.append(child_node)
                if child_caps.event_discovery.value == "TRUE":
                    break
                    
        category = assign_category(seed_node, seed_caps, child_nodes, child_caps_list, seed_html)
        
        sample_event = None
        recent_count = 0
        most_recent = None
        
        for c in [seed_caps] + child_caps_list:
            if c.event_discovery.value == "TRUE":
                sample_event = c.event_discovery
                date_str = c.event_discovery.event_date_if_available
                
                # Simple page context for year
                context = c.event_discovery.evidence_excerpt if c.event_discovery.evidence_excerpt else seed_html[:5000]
                
                d, conf = parse_date_with_context(date_str, context)
                if d:
                    c.event_discovery.event_date_confidence = conf
                    if is_recent(d):
                        recent_count += 1
                        if not most_recent or d > most_recent:
                            most_recent = d
                        
        has_event = (sample_event is not None)
        
        seed_record = {
            "institution": inst,
            "seed_url": seed_url,
            "source_category": category.value,
            "seed_type": seed_node.page_type,
            "event_capability": has_event,
            "recent_event_capable": recent_count > 0,
            "recent_event_count": recent_count,
            "most_recent_event_date": most_recent.strftime("%Y-%m-%d") if most_recent else None,
            "company_capable": sample_event.company_name_if_available is not None if sample_event else False,
            "role_capable": sample_event.role_if_available is not None if sample_event else False,
            "branch_capable": sample_event.branch_if_available is not None if sample_event else False,
            "batch_capable": sample_event.batch_if_available is not None if sample_event else False,
            "ctc_capable": sample_event.ctc_if_available is not None if sample_event else False,
            "contact_capable": seed_caps.has_contact_phone.value == "TRUE" or seed_caps.has_contact_email.value == "TRUE",
            "access_status": seed_node.access_status.value,
            "authentication_status": seed_node.is_auth_wall,
            "crawl_limits": {
                "max_depth": MAX_SOURCE_DEPTH,
                "max_pages": MAX_PAGES_PER_SOURCE,
                "pagination_supported": True
            },
            "evidence": sample_event.evidence_excerpt if sample_event else None,
            "sample_event_url": sample_event.source_url if sample_event else None,
            "source_tree": [n.model_dump() for n in nodes]
        }
        return seed_record

async def main():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for inst, url, purpose in URLS:
            print(f"Verifying {inst} - {url}")
            res = await verify_source_tree(inst, url, browser)
            results.append(res)
            print(f" -> {res['source_category']}")
        await browser.close()
        
    os.makedirs("artifacts", exist_ok=True)
    with open("artifacts/crawl_seed_registry.json", "w", encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
        
    print(f"\nVerification complete. Wrote {len(results)} source trees to artifacts/crawl_seed_registry.json")

if __name__ == "__main__":
    asyncio.run(main())
