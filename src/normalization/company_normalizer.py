import re
from typing import Tuple, List

INVALID_COMPANY_PATTERNS = [
    r'^\s*$', # empty
    r'^[.\s\d]+$', # just numbers and dots (e.g. ". 5.")
    r'^profile$',
    r'^name$',
    r'^company$',
    r'^company name$',
    r'^employer$',
    r'^details$',
    r'^eligibility$',
    r'^branch$',
    r'^click here$',
    r'^read more$',
    r'^date$',
    r'^role$',
    r'placement record',
    r'^placement notice$',
    # Structural/context labels from prompt
    r'^on[- ]?campus$',
    r'^off[- ]?campus$',
    r'^campus$',
    r'^company profile$',
    r'recruitment drive',
    r'placement drive',
    r'^drive$',
    r'^registration$',
    r'^notice$',
    r'^batch$',
]

def normalize_company(raw_name: str) -> Tuple[str, List[str], List[str], bool]:
    """
    Returns (normalized_name, aliases, warnings, is_valid)
    """
    warnings = []
    aliases = []
    if not raw_name:
        return "", aliases, warnings, False

    name = raw_name.strip()
    
    # Plausibility Check
    lower_name = name.lower()
    for pat in INVALID_COMPANY_PATTERNS:
        if re.search(pat, lower_name):
            warnings.append(f"Rejected implausible company candidate: {name}")
            return "", aliases, warnings, False
            
    if len(name) < 2:
        warnings.append(f"Rejected extremely short company candidate: {name}")
        return "", aliases, warnings, False

    # Handle "Formerly known as"
    aka_match = re.search(r'\((formerly|previously) known as (.*?)\)', name, re.IGNORECASE)
    if aka_match:
        aliases.append(aka_match.group(2).strip())
        name = name[:aka_match.start()].strip()
        warnings.append("Company name contained former-name alias")
        
    return name, aliases, warnings, True
