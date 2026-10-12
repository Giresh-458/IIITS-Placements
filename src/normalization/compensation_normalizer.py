import re
from typing import Tuple, Optional, List

def normalize_compensation(ctc_raw: str, text_context: str) -> Tuple[Optional[float], Optional[str], Optional[str], Optional[str], List[str]]:
    """
    Returns (amount, currency, unit, period, warnings)
    """
    warnings = []
    
    if not ctc_raw:
        return None, None, None, None, warnings
        
    c = ctc_raw.lower()
    amount = None
    currency = "INR"
    unit = None
    period = "annual"
    
    # Do not interpret stipend as CTC unless explicitly marked
    if "stipend" in text_context.lower() and "ctc" not in text_context.lower():
        warnings.append("Stipend found but CTC absent")
        return None, None, None, None, warnings

    if "cgpa" in c:
        return None, None, None, None, warnings
        
    match = re.search(r'([\d\.]+)', c)
    if match:
        val = float(match.group(1))
        
        # Enforce compensation context
        if "lpa" in c or "lakhs" in c or "lakh" in c or "ctc" in c or "package" in c or "per annum" in c:
            if "lpa" in c or "lakhs" in c or "lakh" in c:
                unit = "LPA"
                amount = val
            elif val > 100000:
                unit = "INR"
                amount = val
            else:
                amount = val
                warnings.append("CTC unit inferred from explicit annual package wording or missing")
        else:
            warnings.append("Rejected naked number as CTC due to missing context")
            return None, None, None, None, warnings
            
    return amount, currency, unit, period, warnings

def extract_cgpa(text: str) -> Optional[float]:
    match = re.search(r'cgpa.*?([\d\.]+)', text, re.IGNORECASE)
    if not match:
        match = re.search(r'([\d\.]+)\s*(?:cgpa|or above)', text, re.IGNORECASE)
    if match:
        try:
            val = float(match.group(1))
            if 4.0 <= val <= 10.0:
                return val
        except ValueError:
            pass
    return None
