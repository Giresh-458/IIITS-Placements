import re
from typing import List

def normalize_branch(branches: List[str]) -> List[str]:
    normalized = set()
    
    for b in branches:
        b_lower = b.lower()
        if "all branches" in b_lower or "any branch" in b_lower:
            normalized.add("ALL_BRANCHES")
            continue
            
        if "computer science" in b_lower or "cse" in b_lower or "cs" in b_lower:
            normalized.add("CSE")
        if "electronics" in b_lower and "communication" in b_lower or "ece" in b_lower:
            normalized.add("ECE")
        if "information technology" in b_lower or "it" in b_lower:
            normalized.add("IT")
        if "artificial intelligence" in b_lower or "ai" in b_lower:
            if "data" in b_lower or "ds" in b_lower:
                normalized.add("AI_DS")
            else:
                normalized.add("AI")
        if "cyber" in b_lower or "security" in b_lower:
            normalized.add("CYBERSECURITY")
        if "electrical" in b_lower or "eee" in b_lower:
            normalized.add("EEE")
            
    return list(normalized)
