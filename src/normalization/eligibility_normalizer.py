import re
from typing import Tuple, Optional, Dict

def extract_eligibility(text: str) -> Dict[str, str]:
    """
    Extracts backlog and percentage requirements from raw text.
    """
    result = {}
    if not text:
        return result
        
    t = text.lower()
    
    # Backlogs
    if "no active backlog" in t or "no active backlogs" in t:
        result["backlog_requirement"] = "no active backlogs"
    elif "no history of backlog" in t or "no history of backlogs" in t:
        result["backlog_requirement"] = "no history of backlogs"
    elif "0 backlogs" in t:
        result["backlog_requirement"] = "no backlogs"
        
    # Percentages (avoid CGPA overlap if possible)
    perc_match = re.search(r'minimum (\d{2})%', t)
    if perc_match:
        result["percentage_requirement"] = f"Minimum {perc_match.group(1)}%"
        
    return result

def normalize_eligibility(cgpa_raw: str) -> Tuple[Optional[float], list]:
    warnings = []
    if not cgpa_raw:
        return None, warnings
    try:
        # Simple extraction for now
        match = re.search(r'(\d\.\d)', cgpa_raw)
        if match:
            return float(match.group(1)), warnings
    except:
        pass
    return None, warnings
