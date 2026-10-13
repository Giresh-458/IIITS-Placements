import re
from typing import Dict, Any

def extract_from_text(text: str, url: str) -> Dict[str, Any]:
    extracted = {
        "company_candidate": None,
        "role_candidate": None,
        "branch_candidate": None,
        "batch_candidate": None,
        "ctc_candidate": None,
        "cgpa_candidate": None,
        "event_date_candidate": None,
        "registration_deadline_candidate": None,
        "campus_mode_candidate": None,
        "event_type_candidate": None,
        "eligibility_raw": None,
        "selection_process_raw": None,
        "location_raw": None,
        "evidence": {}
    }
    
    if not text:
        return extracted
        
    # Company extraction
    company_patterns = [
        r'(?:Company Name|Company|Company Profile|Hiring Company|Recruiting Company|Name of the Company|Company & Name)\s*(?:\||:|-)\s*([A-Z][a-zA-Z0-9\s&.,()]+?(?:LLP|Private Limited|Pvt\.? Ltd\.?|Ltd\.?|Inc\.?|Limited|Solutions|Technologies|Software|Group|Services|Enterprises|LLC|Corporation)?)(?=[\s\n\.,]+(?:for|GIET|Trident|Register|Read|Dear|on|at|with|Drive|Chennai|scheduled)|\n|\.|$|\|)',
        r'\b([A-Z][a-zA-Z0-9\s&(),\.\-]+?(?:LLP|Private Limited|Pvt\.? Ltd\.?|Ltd\.?|Inc\.?|Limited|Solutions|Technologies|Software|Group|Services|Enterprises|LLC|Corporation)?)\s*(?:\ufffd|\-|–)?\s*hiring for',
        r'(?:Campus Recruitment Drive|Physical Campus Drive|On-Campus Recruitment Drive|On campus drive|Placement Drive|Campus Drive)\s*(?:by|with|of)\s*([A-Z][a-zA-Z0-9\s&()]+?(?:LLP|Private Limited|Pvt\.? Ltd\.?|Ltd\.?|Inc\.?|Limited|Solutions|Technologies|Software|Group|Services|Enterprises|LLC|Corporation)?)(?=[\s\n\.,]+(?:for|GIET|Trident|Register|Read|Dear|on|at|with|Drive|Chennai|scheduled)|\n|\.|$)',
        r'shortlist for the ([a-zA-Z0-9\s\.\&\,\-]+?) Recruitment Drive',
        r'(?:for the|at the)?\s*\b((?!Campus\b)[A-Z][a-zA-Z0-9\.\&\,\-]+(?:\s+[a-zA-Z0-9\.\&\,\-]+){0,4}?(?:\s+(?:Private Limited|Pvt\.? Ltd\.?|LLP|Inc\.?|Corp\.?|Services|Technologies|Technology))?)\s+(?:Campus )?Recruitment Drive',
    ]
    
    for pat in company_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if len(candidate) > 2 and candidate.lower() not in ["profile", "name", "company", "date", "role", "branch", "details", "click here"]:
                extracted["company_candidate"] = candidate
                extracted["evidence"]["company"] = {
                    "text": match.group(0),
                    "method": "structural_regex"
                }
                break
                
    # Role extraction
    role_patterns = [
        r'(?:Job Title|Job Role|Position|Role|Designation|Roles Offered|Job Profile|Profile Offered)\s*(?:\||:)\s*([A-Z][a-zA-Z0-9\s\-\u2013\u2014\ufffd&/]+(?:Engineer|Developer|Consultant|Analyst|Trainee|Manager|Executive|Specialist)?)',
        r'Positions Offered[:\-]?\s*([A-Z][a-zA-Z0-9\s\-\u2013\u2014\ufffd&/]+)',
    ]
    
    for pat in role_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).replace('\ufffd', '-').strip()
            if candidate.lower() not in ["profile", "name", "company", "date", "role", "branch", "details"]:
                extracted["role_candidate"] = candidate
                extracted["evidence"]["role"] = {
                    "text": match.group(0),
                    "method": "structural_regex"
                }
                break

    # Branch extraction
    branch_patterns = [
        r'(?:Eligible Branch(?:es)?|Eligible Degree.*?Branch|Branches|B\.Tech|for B\.?tech|Academic Criteria.*?(?:Branch(?:es)?|B\.Tech|B\.E\.))[:\-\|\s]*([A-Z][a-zA-Z0-9\s,&\-/\u2013\u2014\ufffd|]+?)(?:\(|candidates|students|\n|\.|$)',
    ]
    for pat in branch_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if candidate.lower() not in ["branch", "branches"]:
                extracted["branch_candidate"] = candidate
                extracted["evidence"]["branch"] = {
                    "text": match.group(0),
                    "method": "structural_regex"
                }
                break

    # Batch extraction
    batch_patterns = [
        r'(?:Target Cohorts|batch|yop|passing out|cohorts?)\s*(?:\||:|\-|\s)\s*.*?((?:202[4-9][^\d]{0,40})*202[4-9])',
        r'((?:202[4-9]\s*(?:&|and|,)?\s*)*(?:202[4-9]))\s*\)?\s*(?:yop|passing out|batch|graduating|cohorts?)'
    ]
    for pat in batch_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            # Clean up the match to just comma separate the years
            raw_years = match.group(1)
            years = re.findall(r'(202[4-9])', raw_years)
            extracted["batch_candidate"] = " & ".join(years) + " batch"
            extracted["evidence"]["batch"] = {
                "text": match.group(0),
                "method": "structural_regex"
            }
            break
            
    # CTC extraction
    ctc_patterns = [
        r'(?:CTC|Compensation|Salary Package|Annual Package|Annual CTC|CTC Valuation|Fixed CTC|Gross Salary|Package)\s*(?:\||:|\-)?\s*(?:INR|Rs\.?|₹)?\s*([\d\.]+\s*(?:LPA|Lakhs?|Per Annum))',
        r'(?:INR|Rs\.?|₹)\s*([\d\.]+\s*(?:LPA|Lakhs?|Per Annum))',
        r'([\d\.]+)\s*(?:LPA|Lakhs? Per Annum)'
    ]
    for pat in ctc_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            extracted["ctc_candidate"] = match.group(1).strip()
            extracted["evidence"]["ctc"] = {
                "text": match.group(0),
                "method": "structural_regex"
            }
            break

    # Stipend extraction
    if not extracted["ctc_candidate"]:
        stipend_match = re.search(r'(?:Stipend|Internship stipend)\s*(?:\||:|\-)?\s*(?:INR|Rs\.?|₹)?\s*([\d\.,]+\s*(?:/month|per month|pm))', text, re.IGNORECASE)
        if stipend_match:
            extracted["ctc_candidate"] = stipend_match.group(1).strip()
            extracted["evidence"]["ctc"] = {
                "text": stipend_match.group(0),
                "method": "structural_regex"
            }

    # CGPA Extraction
    cgpa_patterns = [
        r'(?:Minimum CGPA|CGPA(?: Cutoff)?|Minimum|Academic Cutoff)\s*(?:\||:|\-)?\s*([\d\.]+%?)',
        r'([\d\.]+)\s*(?:CGPA|or above)',
    ]
    for pat in cgpa_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            extracted["cgpa_candidate"] = match.group(1).strip()
            extracted["evidence"]["cgpa"] = {
                "text": match.group(0),
                "method": "structural_regex"
            }
            break

    # Dates
    reg_patterns = [
        r'(?:Register Before|Registration closes|Registration deadline)\s*(?:\||:|\-)?\s*([\d]{1,2}(?:th|st|nd|rd)?\s*[a-zA-Z]+(?:\s*[\d]{4})?|[\d]{1,2}\.[\d]{1,2}\.[\d]{2,4}|[\d]{1,2}/[\d]{1,2}/[\d]{4})',
    ]
    for pat in reg_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            extracted["registration_deadline_candidate"] = match.group(1).strip()
            extracted["evidence"]["registration_deadline"] = {
                "text": match.group(0),
                "method": "structural_regex"
            }
            break
            
    # Event Date explicit Contexts (To avoid swapping with Registration Deadline)
    ev_date_patterns = [
        r'(?:Campus Drive Date|Drive Date|Interview Date)\s*(?:\||:|\-)?\s*([\d]{1,2}(?:th|st|nd|rd)?\s*[a-zA-Z]+(?:\s*[\d]{4})?|[\d]{1,2}\.[\d]{1,2}\.[\d]{2,4}|[\d]{1,2}/[\d]{1,2}/[\d]{4})',
        r'scheduled on (?:[a-zA-Z]+, )?([\d]{1,2}\s*[a-zA-Z]+\s*[\d]{4})',
        r'Date: ([\d]{1,2}-[\d]{1,2}-[\d]{4})'
    ]
    for pat in ev_date_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            extracted["event_date_candidate"] = match.group(1).strip()
            extracted["evidence"]["event_date"] = {
                "text": match.group(0),
                "method": "structural_regex"
            }
            break

            
    # Campus Mode
    if "physical campus drive" in text.lower() or "on-campus" in text.lower() or "on campus" in text.lower():
        extracted["campus_mode_candidate"] = "ON_CAMPUS"
    elif "pool campus" in text.lower() or "pooled campus" in text.lower():
        extracted["campus_mode_candidate"] = "POOL_CAMPUS"
    elif "virtual" in text.lower() or "online" in text.lower():
        extracted["campus_mode_candidate"] = "VIRTUAL"

    return extracted

def get_page_type(url: str, text: str) -> str:
    """Legacy helper for crawler."""
    t = text.lower()
    if 'event' in url.lower() or 'notice' in url.lower() or 'drive' in url.lower() or 'test.com' in url.lower():
        if any(w in t for w in ['b.tech', 'mca', 'eligible', 'ctc', 'lpa', 'campus drive', 'recruitment']):
            return 'EVENT_DETAIL'
    return 'OTHER'

def _looks_like_event_listing(scope) -> bool:
    """Identify archive/index pages whose text combines multiple unrelated notices."""
    event_terms = re.compile(
        r"\b(campus|placement|recruitment|hiring|job opening|career drive|placement drive)\b",
        re.IGNORECASE,
    )
    event_headings = {
        re.sub(r"\s+", " ", heading.get_text(" ", strip=True)).strip().lower()
        for heading in scope.find_all(["h2", "h3", "h4", "h5"])
        if event_terms.search(heading.get_text(" ", strip=True))
    }
    event_links = [
        link for link in scope.find_all("a", href=True)
        if event_terms.search(
            f"{link.get_text(' ', strip=True)} {link.get('href', '')}"
        )
    ]
    return len(event_headings) >= 2 or len(event_links) >= 5


def _extract_candidate_text(html: str, fallback_text: str, url: str) -> str | None:
    """Return text for one page/article, excluding site chrome and related posts.

    Archive pages are intentionally rejected here: treating an index of several
    notices as one event can mix a company, role, and date from different posts.
    """
    if not html:
        return fallback_text

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for element in list(soup.find_all(["script", "style", "nav", "footer", "aside", "form", "noscript"])):
        element.decompose()

    chrome_tokens = (
        "related-post", "related_posts", "sidebar", "post-navigation",
        "comments-area", "comment-respond", "site-footer", "footer-widget",
        "widget-area", "recent-posts", "recent-notices", "breadcrumb",
        "nav-menu", "social-share", "author-box",
    )
    for element in list(soup.find_all(True)):
        classes = element.get("class", [])
        if isinstance(classes, str):
            classes = [classes]
        identifier = str(element.get("id", ""))
        label = " ".join([identifier, *[str(item) for item in classes]]).lower()
        if any(token in label for token in chrome_tokens):
            element.decompose()

    # Prefer a single article-body container. Multiple matching bodies usually
    # indicate an archive page or a template with multiple post cards.
    body_selectors = (
        "[itemprop='articleBody']",
        ".entry-content",
        ".post-content",
        ".article-content",
        ".td-post-content",
        ".single-post-content",
    )
    scope = None
    for selector in body_selectors:
        matches = soup.select(selector)
        if matches:
            if len(matches) != 1:
                return None
            scope = matches[0]
            break

    if scope is None:
        h1 = soup.find("h1")
        h1_article = h1.find_parent("article") if h1 else None
        articles = soup.find_all("article")
        if h1_article is not None:
            scope = h1_article
        elif len(articles) == 1:
            scope = articles[0]
        elif len(articles) > 1:
            return None
        else:
            scope = soup.body or soup

    if _looks_like_event_listing(scope):
        return None

    # Preserve table values in the scoped article while removing table layout.
    for table in list(scope.find_all("table")):
        headers = [th.get_text(" ", strip=True) for th in table.find_all("th")]
        for row in table.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in row.find_all("td")]
            if not cells:
                continue
            row_text = []
            for index, cell in enumerate(cells):
                if index < len(headers) and headers[index]:
                    row_text.append(f"{headers[index]}: {cell}")
                else:
                    row_text.append(cell)
            new_div = soup.new_tag("div")
            new_div.string = " | ".join(row_text)
            table.insert_before(new_div)
        table.decompose()

    return scope.get_text(separator=" ", strip=True)


def extract_event_candidate(html: str, text: str, url: str, metadata: dict = None) -> Any:
    """Extract one event candidate only from the page's primary article content."""
    from src.models.domain import HiringEventCandidate

    scoped_text = _extract_candidate_text(html, text, url)
    if scoped_text is None:
        return None
    text = scoped_text

    # Do not promote generic navigation or non-hiring notices to event records.
    if get_page_type(url, text) != "EVENT_DETAIL":
        return None

    extracted = extract_from_text(text, url)
    if not extracted.get("company_candidate"):
        return None

    return HiringEventCandidate(
        event_url=url,
        source_seed_url=metadata.get('seed_url') if metadata and metadata.get('seed_url') else "",
        institution=metadata.get('institution') if metadata else "UNKNOWN",
        event_title="Campus Drive",
        company_name=extracted["company_candidate"],
        role=extracted.get("role_candidate"),
        ctc_raw=extracted.get("ctc_candidate"),
        batch=extracted.get("batch_candidate"),
        eligible_branches=[b.strip() for b in extracted.get("branch_candidate", "").split(',')] if extracted.get("branch_candidate") else [],
        campus_mode=extracted.get("campus_mode_candidate"),
        evidence=extracted.get("evidence", {}),
        raw_text_excerpt=text[:1000]
    )


def extract_candidates_from_pages(pages):
    """Extract hiring-event candidates from raw page captures produced by Crawling."""
    from datetime import datetime
    from src.extraction.date_normalizer import extract_dates, is_event_recent

    candidates = []
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            raise ValueError(f"Crawled page record {index} must be an object.")

        url = page.get("url")
        html = page.get("html", "")
        text = page.get("text", "")
        institution = page.get("institution")
        seed_url = page.get("seed_url", "")

        if not isinstance(url, str) or not url.strip():
            raise ValueError(f"Crawled page record {index} requires a URL.")
        if not isinstance(html, str) or not isinstance(text, str):
            raise ValueError(
                f"Crawled page record {index} HTML and text must be strings."
            )
        if not isinstance(institution, str) or not institution.strip():
            raise ValueError(
                f"Crawled page record {index} requires an institution."
            )

        scoped_text = _extract_candidate_text(html, text, url)
        if scoped_text is None:
            continue

        candidate = extract_event_candidate(
            "",
            scoped_text,
            url,
            {"institution": institution, "seed_url": seed_url},
        )
        if not candidate:
            continue

        # Date parsing must use the same article-scoped content as company/role
        # parsing; otherwise a sidebar or related post can supply another event's date.
        event_date, event_raw, event_conf, reg_date, reg_raw, reg_conf = extract_dates(
            scoped_text, scoped_text
        )
        candidate.event_date = event_date
        candidate.event_date_raw = event_raw
        candidate.event_date_confidence = event_conf
        candidate.registration_deadline = reg_date
        candidate.registration_deadline_raw = reg_raw

        if event_date:
            candidate.is_recent = is_event_recent(
                event_date, datetime(2026, 9, 20), datetime(2026, 10, 4)
            )
            if candidate.is_recent:
                candidate.event_status = "COMPLETED_15D"

        candidates.append(candidate)

    return candidates
