from src.evidence.rehydrator import rehydrate_url
from src.extraction.event_extractor import extract_event_candidate
import sys

def test_url(url, institution, expected_company=None):
    print(f"\nTesting {institution}: {url}")
    rehydrated = rehydrate_url(url)
    if not rehydrated:
        print("Failed to rehydrate")
        return
        
    corpus = [rehydrated["title"]] + rehydrated["headings"] + rehydrated["tables"] + rehydrated["paragraphs"] + rehydrated["lists"]
    for j in rehydrated.get("json_ld", []):
        if isinstance(j, dict):
            if "startDate" in j: corpus.append(f"Campus Drive Date | {j['startDate']}")
            if "organizer" in j and isinstance(j["organizer"], dict) and "name" in j["organizer"]: corpus.append(f"Company Name | {j['organizer']['name']}")
            if "name" in j and j.get("@type") == "Event": corpus.append(f"Job Title | {j['name']}")
    
    full_text = "\n".join(corpus)
    cand = extract_event_candidate(full_text, full_text, url, {"institution": institution})
    if not cand:
        print("Candidate is None (Rejected by get_page_type or no data extracted)")
        return
    print(f"Company: {cand.company_name}")
    print(f"Role: {cand.role}")
    print(f"Branch: {cand.eligible_branches}")
    print(f"Batch: {cand.batch}")
    print(f"CTC: {cand.ctc_raw}")
    print(f"Date: {cand.event_date_raw}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_url(sys.argv[1], "Test")
    else:
        test_url("https://trident.ac.in/placementnotice/physical-campus-drive-by-injotech-india-private-limited-for-b-tech-eeemech-civil-candidates-of-2026-2027-yop-register-before-02-10-26", "Trident")
        test_url("https://giet.edu.in/event/", "GIET")
        test_url("https://hub.rgukt.ac.in/hub/tnp/index", "RGUKT") 
        test_url("https://aaaenggcoll.ac.in/placement/", "AAA")
