import re
import uuid
import time
from datetime import datetime
from typing import List, Dict, Any

from duckduckgo_search import DDGS
import httpx
from bs4 import BeautifulSoup

from src.models.contact import (
    NormalizedContact, ContactRole, ContactSide, PhoneVerificationState,
    ConfidenceLevel, ContactCurrentness
)
from src.verification.contact_verifier import is_likely_phone

def generate_queries(company_name: str) -> List[str]:
    # Bounded queries per company
    return [
        f'"{company_name}" HR OR "Talent Acquisition" OR "Campus Recruitment" contact phone',
        f'"{company_name}" recruiter phone number'
    ]

def map_role_from_text(text: str) -> ContactRole:
    text_lower = text.lower()
    if "college" in text_lower or "placement officer" in text_lower or "t&p" in text_lower:
        return ContactRole.COLLEGE_CONTACT
    if "campus recruit" in text_lower or "university recruit" in text_lower:
        return ContactRole.CAMPUS_RECRUITMENT
    if "talent acquisition" in text_lower:
        return ContactRole.TALENT_ACQUISITION
    if "hr " in text_lower or "human resources" in text_lower:
        return ContactRole.DIRECT_HR
    if "recruiter" in text_lower or "hiring" in text_lower:
        return ContactRole.RECRUITER
    if "sales" in text_lower:
        return ContactRole.SALES
    if "support" in text_lower or "customer service" in text_lower:
        return ContactRole.CUSTOMER_SUPPORT
    return ContactRole.UNKNOWN

def map_side_from_role(role: ContactRole) -> ContactSide:
    if role == ContactRole.COLLEGE_CONTACT:
        return ContactSide.COLLEGE
    elif role in [
        ContactRole.DIRECT_HR, ContactRole.TALENT_ACQUISITION, ContactRole.CAMPUS_RECRUITMENT,
        ContactRole.UNIVERSITY_RECRUITMENT, ContactRole.RECRUITER, ContactRole.HIRING_MANAGER,
        ContactRole.HR_HELPDESK, ContactRole.COMPANY_SWITCHBOARD, ContactRole.CUSTOMER_SUPPORT, ContactRole.SALES
    ]:
        return ContactSide.COMPANY
    return ContactSide.UNKNOWN

def extract_phones_from_text(text: str) -> List[str]:
    # Regex to catch Indian mobile/landline-ish numbers or international formats, very broadly.
    pattern = r'(?:\+?91[\-\s]?)?[6-9]\d{2}[\-\s]?\d{3}[\-\s]?\d{4}|\b0\d{2,4}[\-\s]?\d{6,8}\b'
    matches = re.findall(pattern, text)
    phones = []
    for m in set(matches):
        clean = re.sub(r'[\s\-\(\)\+]', '', m)
        if is_likely_phone(clean):
            phones.append(m.strip())
    return phones

class BoundedDiscoveryEngine:
    def __init__(self):
        self.telemetry = {
            "queries_generated": 0,
            "urls_discovered": 0,
            "urls_attempted": 0,
            "successful_fetches": 0,
            "failed_fetches": 0,
            "pages_fetched": 0,
            "browser_pages_fetched": 0,
            "HTTP_fetches": 0,
            "retries": 0,
            "exceptions": 0,
            "stop_reason": "COMPLETED"
        }
        self.per_company_telemetry = {}
        self.source_level_lineage = []
        self.client = httpx.Client(timeout=10.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

    def attempt_live_discovery(self, company_name: str, canonical_id: str) -> List[NormalizedContact]:
        candidates = []
        if company_name not in self.per_company_telemetry:
            self.per_company_telemetry[company_name] = {
                "queries_generated": 0,
                "urls_discovered": 0,
                "urls_attempted": 0,
                "successful_fetches": 0,
                "failed_fetches": 0,
                "pages_fetched": 0,
                "phone_candidates_found": 0,
                "stop_reason": "COMPLETED"
            }
            
        queries = generate_queries(company_name)
        self.telemetry["queries_generated"] += len(queries)
        self.per_company_telemetry[company_name]["queries_generated"] += len(queries)
        
        urls_to_fetch = {}
        
        try:
            with DDGS() as ddgs:
                for q in queries:
                    # Bounded search: max 3 results per query
                    results = list(ddgs.text(q, max_results=3))
                    for r in results:
                        url = r.get("href")
                        if url and url not in urls_to_fetch and len(urls_to_fetch) < 4: # max 4 URLs per company
                            self.telemetry["urls_discovered"] += 1
                            self.per_company_telemetry[company_name]["urls_discovered"] += 1
                            urls_to_fetch[url] = {"snippet": r.get("body", ""), "query": q}
        except Exception as e:
            self.telemetry["exceptions"] += 1
            self.per_company_telemetry[company_name]["stop_reason"] = "API_RATE_LIMIT"
            print(f"Search exception for {company_name}: {e}")
            
        for url, data in urls_to_fetch.items():
            snippet = data["snippet"]
            query = data["query"]
            
            # Basic filtering of obvious irrelevant domains
            if "linkedin.com" in url or "glassdoor.com" in url:
                continue
                
            self.telemetry["urls_attempted"] += 1
            self.per_company_telemetry[company_name]["urls_attempted"] += 1
            self.telemetry["HTTP_fetches"] += 1
            
            lineage_record = {
                "company": company_name,
                "query": query,
                "url": url,
                "domain": url.split("//")[-1].split("/")[0],
                "retrieval_timestamp": datetime.utcnow().isoformat() + "Z",
                "fetch_method": "HTTP",
                "success": False,
                "http_status": None,
                "page_title": None,
                "phone_candidates_found": 0,
                "extraction_result": "Failed to fetch"
            }
            
            try:
                resp = self.client.get(url)
                lineage_record["http_status"] = resp.status_code
                
                if resp.status_code == 200:
                    self.telemetry["successful_fetches"] += 1
                    self.telemetry["pages_fetched"] += 1
                    self.per_company_telemetry[company_name]["successful_fetches"] += 1
                    self.per_company_telemetry[company_name]["pages_fetched"] += 1
                    lineage_record["success"] = True
                    
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    if soup.title and soup.title.string:
                        lineage_record["page_title"] = soup.title.string.strip()
                        
                    text_content = soup.get_text(separator=' ', strip=True)
                    
                    # Combine snippet and page text for evidence
                    full_evidence = snippet + " | " + text_content[:500] 
                    phones = extract_phones_from_text(text_content)
                    
                    if not phones:
                        # try snippet
                        phones = extract_phones_from_text(snippet)
                        
                    lineage_record["phone_candidates_found"] = len(phones)
                    self.per_company_telemetry[company_name]["phone_candidates_found"] += len(phones)
                    
                    if len(phones) == 0:
                        lineage_record["extraction_result"] = "No contextually valid phone candidates found"
                    else:
                        lineage_record["extraction_result"] = f"Found {len(phones)} candidates"
                        
                    for phone in phones:
                        role = map_role_from_text(full_evidence)
                        side = map_side_from_role(role)
                        
                        comp_conf = ConfidenceLevel.LOW
                        if company_name.lower() in url.lower() or company_name.lower() in snippet.lower() or company_name.lower() in (soup.title.string.lower() if soup.title else ""):
                            comp_conf = ConfidenceLevel.HIGH
                            
                        rel_conf = ConfidenceLevel.LOW
                        if role in [ContactRole.DIRECT_HR, ContactRole.TALENT_ACQUISITION, ContactRole.CAMPUS_RECRUITMENT]:
                            rel_conf = ConfidenceLevel.HIGH
                        
                        c = NormalizedContact(
                            contact_id=str(uuid.uuid4()),
                            company_canonical_id=canonical_id,
                            company_name=company_name,
                            contact_role=role,
                            contact_side=side,
                            phone_raw=phone,
                            phone_normalized=re.sub(r'[\s\-\(\)]', '', phone),
                            source_url=url,
                            source_type="PUBLIC_WEB",
                            evidence_text=snippet,
                            evidence_location="Web search result/Page text",
                            retrieved_at=datetime.utcnow().isoformat(),
                            company_match_confidence=comp_conf,
                            recruitment_relevance_confidence=rel_conf
                        )
                        candidates.append(c)
                else:
                    self.telemetry["failed_fetches"] += 1
                    self.per_company_telemetry[company_name]["failed_fetches"] += 1
                    lineage_record["extraction_result"] = f"HTTP Error {resp.status_code}"
            except Exception as e:
                self.telemetry["exceptions"] += 1
                self.telemetry["failed_fetches"] += 1
                self.per_company_telemetry[company_name]["failed_fetches"] += 1
                lineage_record["extraction_result"] = f"Exception: {str(e)}"
                
            self.source_level_lineage.append(lineage_record)
            time.sleep(1) # rate limiting
            
        # Update stop reason if we encountered network failures across the board
        if self.per_company_telemetry[company_name]["urls_attempted"] > 0 and self.per_company_telemetry[company_name]["successful_fetches"] == 0 and self.per_company_telemetry[company_name]["failed_fetches"] > 0:
            if self.per_company_telemetry[company_name]["stop_reason"] == "COMPLETED":
                self.per_company_telemetry[company_name]["stop_reason"] = "NETWORK_FAILURE"
                
        return candidates
