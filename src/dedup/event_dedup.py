from typing import List
import hashlib
from src.models.domain import HiringEventCandidate

def deduplicate_events(events: List[HiringEventCandidate]) -> List[HiringEventCandidate]:
    """
    Deduplicate based on institution, company name, and event date.
    Prefer events with higher confidence or more fields.
    """
    grouped = {}
    for ev in events:
        key = f"{ev.institution}_{ev.company_name or 'UNKNOWN'}_{ev.event_date.date() if ev.event_date else 'UNKNOWN'}"
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(ev)
        
    deduplicated = []
    for key, group in grouped.items():
        if len(group) == 1:
            deduplicated.append(group[0])
        else:
            # Score each to find the best
            def score(e):
                return sum(1 for v in [e.role, e.ctc, e.batch, e.eligible_branches] if v)
                
            group.sort(key=score, reverse=True)
            best = group[0]
            # Merge evidence if possible, simplified here
            deduplicated.append(best)
            
    return deduplicated

def normalize_url(url: str) -> str:
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), parsed.params, parsed.query, ''))
