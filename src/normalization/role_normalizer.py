import re
from typing import Tuple

INVALID_ROLE_PATTERNS = [
    r'^\s*$',
    r'^[.\s\d]+$', 
    r'^profile$',
    r'^name$',
    r'^role$',
    r'^designation$',
    r'^position$',
    r'^branch$',
    r'^branches$',
    r'^department$'
]

def normalize_role(raw_role: str) -> Tuple[str, str, str, bool]:
    """
    Returns (role_family, role_subtype, warnings, is_valid)
    """
    warnings = ""
    if not raw_role:
        return "UNKNOWN", "", warnings, False

    r = raw_role.strip().lower()
    
    for pat in INVALID_ROLE_PATTERNS:
        if re.search(pat, r):
            warnings = f"Rejected implausible role candidate: {raw_role}"
            return "UNKNOWN", "", warnings, False
    
    if any(x in r for x in ["software", "sde", "developer", "backend", "frontend", "web", "full stack", "fullstack"]):
        family = "SOFTWARE_ENGINEERING"
        subtype = "FULL_STACK" if "full" in r else ("BACKEND" if "backend" in r else ("FRONTEND" if "frontend" in r else "SDE"))
    elif any(x in r for x in ["ai", "ml", "machine learning", "artificial intelligence", "genai", "llm", "nlp"]):
        family = "AI_ML"
        subtype = "AI_ENGINEER" if "ai" in r else "ML_ENGINEER"
    elif any(x in r for x in ["data", "analytics"]):
        family = "DATA_ENGINEERING" if "engineer" in r else "DATA_SCIENCE"
        subtype = "DATA_ENGINEER"
    elif any(x in r for x in ["devops", "cloud", "sre", "platform"]):
        family = "CLOUD_DEVOPS"
        subtype = "DEVOPS"
    elif any(x in r for x in ["cyber", "security"]):
        family = "CYBERSECURITY"
        subtype = "SECURITY_ENGINEER"
    elif any(x in r for x in ["qa", "automation", "test"]):
        family = "QA_AUTOMATION"
        subtype = "QA_ENGINEER"
    elif any(x in r for x in ["embedded", "iot", "firmware"]):
        family = "EMBEDDED_IOT"
        subtype = "EMBEDDED_ENGINEER"
    elif any(x in r for x in ["network", "system"]):
        family = "NETWORKING_SYSTEMS"
        subtype = "SYSTEMS_ENGINEER"
    elif any(x in r for x in ["solutions", "support"]):
        family = "IT_SUPPORT"
        subtype = "TECHNICAL_SUPPORT"
    else:
        family = "UNKNOWN"
        subtype = ""
        return family, subtype, warnings, True # Valid but unknown family
        
    return family, subtype, warnings, True
