import re
from typing import Tuple, Optional, List

def normalize_batch(batch_raw: str) -> Tuple[Optional[int], List[str]]:
    warnings = []
    if not batch_raw:
        return None, warnings
        
    b = batch_raw.lower()
    
    if "final year" in b:
        warnings.append("Year inferred from page context (final year)")
        return None, warnings
        
    match = re.search(r'(202[4-9])', b)
    if match:
        if "batch" in b or "yop" in b or "graduating" in b or "pass" in b:
            return int(match.group(1)), warnings
        else:
            warnings.append("Rejected year extraction without batch context")
            return None, warnings
        
    return None, warnings

def normalize_campus_mode(mode_raw: str, text_context: str) -> str:
    if mode_raw:
        mr = mode_raw.lower()
        if "on-campus" in mr or "on campus" in mr or "on_campus" in mr: return "ON_CAMPUS"
        if "off-campus" in mr or "off campus" in mr or "off_campus" in mr: return "OFF_CAMPUS"
        if "pool" in mr: return "POOL_CAMPUS"
        if "joint" in mr: return "JOINT_CAMPUS"
        if "virtual" in mr or "online" in mr: return "VIRTUAL"
        if "hybrid" in mr: return "HYBRID"
        
    tc = text_context.lower() if text_context else ""
    if "on-campus recruitment" in tc or "on campus drive" in tc: return "ON_CAMPUS"
    if "pool campus" in tc: return "POOL_CAMPUS"
    if "virtual recruitment" in tc: return "VIRTUAL"
    
    return "UNKNOWN"

def normalize_event_type(type_raw: str, text_context: str) -> str:
    tc = (type_raw + " " + (text_context or "")).lower()
    
    if "internship" in tc: return "INTERNSHIP_HIRING"
    if "pre-placement" in tc or "ppo" in tc: return "PRE_PLACEMENT"
    if "walk-in" in tc: return "WALK_IN"
    if "campus recruitment" in tc or "placement drive" in tc: return "CAMPUS_RECRUITMENT"
    
    return "UNKNOWN"
