import re
from typing import Dict, Any


def _normalize_company_candidate(value: str) -> str:
    """Collapse layout whitespace before storing a company name."""
    return re.sub(r"\s+", " ", value or "").strip(" \t\r\n:;,-–—")


def _is_plausible_company_candidate(value: str) -> bool:
    """Reject obvious social-navigation bundles and fragments of sentence text."""
    candidate = _normalize_company_candidate(value)
    if not candidate:
        return False

    tokens = re.findall(r"[a-z0-9]+", candidate.lower())
    if not tokens or len(tokens) > 7:
        return False

    social_labels = {"linkedin", "instagram", "whatsapp", "youtube", "facebook", "twitter"}
    if sum(token in social_labels for token in tokens) >= 2:
        return False

    if re.search(
        r"\b(?:will be conducting|is conducting|are conducting|will conduct|"
        r"conducting a|conducting the|will be held|is being held)\b",
        candidate,
        re.IGNORECASE,
    ):
        return False

    invalid_start_tokens = {
        "limited", "private", "will", "would", "be", "being", "conducting",
        "a", "an", "the", "and", "or", "by", "for", "of", "with", "on", "to", "in", "at",
    }
    invalid_end_tokens = {
        "will", "would", "be", "being", "conducting", "a", "an", "the",
        "and", "or", "by", "for", "of", "with", "on", "to", "in", "at",
        "campus", "recruitment", "drive",
    }
    if tokens[0] in invalid_start_tokens or tokens[-1] in invalid_end_tokens:
        return False

    return True

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
        
    # Prefer a bounded company span before generic sentence text, e.g.
    # "ITC Limited will be conducting a Campus Recruitment Drive".
    name_token = r"[A-Z][A-Za-z0-9&.,'()/+\-]*"
    suffix_token = (
        r"(?i:pvt\.?|private|ltd\.?|limited|llp|inc\.?|corp\.?|"
        r"corporation|industries|solutions|services|technologies|group)"
    )
    conducting_pattern = (
        r"\b("
        + name_token
        + r"(?:[ \t]+(?:" + name_token + r"|" + suffix_token + r")){0,5}"
        + r")[ \t\r\n]+(?i:will be conducting|is conducting|are conducting|will conduct)"
        + r"[ \t\r\n]+(?:(?i:a|the)[ \t\r\n]+)?"
        + r"(?i:campus[ \t\r\n]+)?(?i:recruitment|placement|hiring)[ \t\r\n]+drive\b"
    )
    conducting_match = re.search(conducting_pattern, text)
    if conducting_match:
        candidate = _normalize_company_candidate(conducting_match.group(1))
        if _is_plausible_company_candidate(candidate):
            extracted["company_candidate"] = candidate
            extracted["evidence"]["company"] = {
                "text": _normalize_company_candidate(conducting_match.group(0)),
                "method": "sentence_context_regex",
            }

    # Company extraction
    company_patterns = [
        r"^\s*([A-Z][A-Za-z0-9&.,'() ]{1,60}?)\s*[–—-]\s*(?:GD Schedule\b|Group Discussion\b|Interview Schedule\b|Virtual Campus Drive\b|Campus Drive\b|Recruitment Drive\b)",
        r'(?:Company Name|Company|Company Profile|Hiring Company|Recruiting Company|Name of the Company|Company & Name)\s*(?:\||:|-)\s*([A-Z][a-zA-Z0-9\s&.,()]+?(?:LLP|Private Limited|Pvt\.? Ltd\.?|Ltd\.?|Inc\.?|Limited|Solutions|Technologies|Software|Group|Services|Enterprises|LLC|Corporation)?)(?=[\s\n\.,]+(?:for|GIET|Trident|Register|Read|Dear|on|at|with|Drive|Chennai|scheduled)|\n|\.|$|\|)',
        r'\b([A-Z][a-zA-Z0-9\s&(),\.\-]+?(?:LLP|Private Limited|Pvt\.? Ltd\.?|Ltd\.?|Inc\.?|Limited|Solutions|Technologies|Software|Group|Services|Enterprises|LLC|Corporation)?)\s*(?:\ufffd|\-|–)?\s*hiring for',
        r'(?:Campus Recruitment Drive|Physical Campus Drive|On-Campus Recruitment Drive|On campus drive|Placement Drive|Campus Drive)\s*(?:by|with|of)\s*([A-Z][a-zA-Z0-9\s&()]+?(?:LLP|Private Limited|Pvt\.? Ltd\.?|Ltd\.?|Inc\.?|Limited|Solutions|Technologies|Software|Group|Services|Enterprises|LLC|Corporation)?)(?=[\s\n\.,]+(?:for|GIET|Trident|Register|Read|Dear|on|at|with|Drive|Chennai|scheduled)|\n|\.|$)',
        r'shortlist for the ([a-zA-Z0-9\s\.\&\,\-]+?) Recruitment Drive',
        # Horizontal whitespace prevents social links on separate lines from
        # being joined into a fake company name.
        r'(?:for the|at the)?[ \t]*\b((?!Campus\b)[A-Z][a-zA-Z0-9\.\&\,\-]+(?:[ \t]+[a-zA-Z0-9\.\&\,\-]+){0,4}?(?:[ \t]+(?:Private Limited|Pvt\.? Ltd\.?|LLP|Inc\.?|Corp\.?|Services|Technologies|Technology))?)[ \t]+(?:Campus[ \t]+)?Recruitment Drive',
    ]
    
    if not extracted["company_candidate"]:
        for pat in company_patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if not match:
                continue
            candidate = _normalize_company_candidate(match.group(1))
            if len(candidate) <= 2 or not _is_plausible_company_candidate(candidate):
                continue
            if candidate.lower() in ["profile", "name", "company", "date", "role", "branch", "details", "click here"]:
                continue
            extracted["company_candidate"] = candidate
            extracted["evidence"]["company"] = {
                "text": _normalize_company_candidate(match.group(0)),
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

            
    # Campus mode must be supported by hiring-event context. Generic site text
    # such as "ONLINE FEE PAYMENT" must not classify an unrelated drive as virtual.
    extracted["campus_mode_candidate"] = _infer_campus_mode(text)

    return extracted


def _infer_campus_mode(text: str) -> str | None:
    """Infer mode only from explicit drive-mode phrases, not generic page words."""
    normalized = re.sub(r"\s+", " ", text or "").lower()

    if re.search(
        r"\bphysical\s+campus\s+drive\b"
        r"|\bon[- ]campus\s+(?:recruitment\s+)?drive\b"
        r"|\bmode\s+of\s+(?:the\s+)?drive\s*[:|=-]\s*physical\b",
        normalized,
    ):
        return "ON_CAMPUS"

    if re.search(
        r"\b(?:pool|pooled)\s+campus\s+(?:recruitment\s+)?drive\b"
        r"|\bmode\s+of\s+(?:the\s+)?drive\s*[:|=-]\s*(?:pool|pooled)\b",
        normalized,
    ):
        return "POOL_CAMPUS"

    if re.search(
        r"\b(?:virtual|online)\s+(?:campus\s+)?(?:recruitment\s+)?drive\b"
        r"|\bmode\s+of\s+(?:the\s+)?drive\s*[:|=-]\s*(?:virtual|online)\b"
        r"|\b(?:campus\s+)?drive\s+(?:will be|is being|was)\s+"
        r"(?:held|conducted)\s+(?:online|virtually)\b",
        normalized,
    ):
        return "VIRTUAL"

    return None

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
    """Return one page's primary content without site chrome or related posts."""
    if not html:
        return fallback_text

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # Scope a detail page to its title's article BEFORE removing site-wide
    # chrome. Some themes wrap post content in containers whose classes look
    # like related/recent-post areas; deleting those from the document first
    # can accidentally detach the primary article or its body.
    heading = soup.find("h1", class_="entry-title")
    if heading is None:
        first_h1 = soup.find("h1")
        if first_h1 is not None and first_h1.find_parent("article") is not None:
            heading = first_h1

    primary_article = heading.find_parent("article") if heading else None
    if primary_article is not None:
        title_text = heading.get_text(" ", strip=True)
        isolated_soup = BeautifulSoup(str(primary_article), "html.parser")
        scope = isolated_soup.find("article") or isolated_soup

        for element in list(
            scope.find_all(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"])
        ):
            if element.parent is not None and getattr(element, "attrs", None) is not None:
                element.decompose()

        chrome_tokens = (
            "related-post", "related_posts", "sidebar", "post-navigation",
            "comments-area", "comment-respond", "site-footer", "footer-widget",
            "widget-area", "recent-posts", "recent-notices", "breadcrumb",
            "nav-menu", "social-share", "author-box", "post-meta",
        )
        for element in list(scope.find_all(True)):
            if element.parent is None or getattr(element, "attrs", None) is None:
                continue
            classes = element.get("class", [])
            if isinstance(classes, str):
                classes = [classes]
            identifier = str(element.get("id", ""))
            label = " ".join([identifier, *[str(item) for item in classes]]).lower()
            if any(token in label for token in chrome_tokens):
                element.decompose()

        # Body selectors are evaluated only inside the primary article, so
        # sibling related-post cards cannot create selector ambiguity.
        body_selectors = (
            "[itemprop='articleBody']",
            ".entry-content",
            ".post-content",
            ".article-content",
            ".td-post-content",
            ".single-post-content",
        )
        body_scope = scope
        for selector in body_selectors:
            matches = scope.select(selector)
            if len(matches) == 1:
                body_scope = matches[0]
                break

        for table in list(body_scope.find_all("table")):
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
                new_div = isolated_soup.new_tag("div")
                new_div.string = " | ".join(row_text)
                table.insert_before(new_div)
            table.decompose()

        body_text = body_scope.get_text(separator="\n", strip=True)
        if title_text and title_text.lower() not in body_text.lower():
            return f"{title_text}\n{body_text}".strip()
        return body_text

    # No article-scoped H1: handle archive pages and themes without <article>.
    # Strip semantic chrome first, including the <header> used for institutional
    # navigation on pages such as AAA College's placement detail page.
    for element in list(
        soup.find_all(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"])
    ):
        if element.parent is not None and getattr(element, "attrs", None) is not None:
            element.decompose()

    chrome_tokens = (
        "related-post", "related_posts", "sidebar", "post-navigation",
        "comments-area", "comment-respond", "site-footer", "footer-widget",
        "widget-area", "recent-posts", "recent-notices", "breadcrumb",
        "nav-menu", "social-share", "author-box", "site-header", "masthead",
        "site-navigation", "main-navigation", "primary-navigation",
        "header-widget", "header-top", "top-bar", "skip-link",
    )
    for element in list(soup.find_all(True)):
        if element.parent is None or getattr(element, "attrs", None) is None:
            continue
        classes = element.get("class", [])
        if isinstance(classes, str):
            classes = [classes]
        identifier = str(element.get("id", ""))
        label = " ".join([identifier, *[str(item) for item in classes]]).lower()
        if any(token in label for token in chrome_tokens):
            element.decompose()

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
        articles = soup.find_all("article")
        if len(articles) == 1:
            scope = articles[0]
        elif len(articles) > 1:
            return None
        else:
            main_regions = soup.find_all("main")
            if len(main_regions) == 1:
                scope = main_regions[0]
            elif len(main_regions) > 1:
                return None
            else:
                scope = soup.body or soup

    if _looks_like_event_listing(scope):
        return None

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

    return scope.get_text(separator="\n", strip=True)

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
