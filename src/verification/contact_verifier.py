import re
from typing import Dict, Any, List, Optional
from src.models.contact import (
    NormalizedContact, ContactRole, ContactSide, PhoneVerificationState,
    ContactCurrentness, ConfidenceLevel
)

def is_likely_phone(text: str) -> bool:
    """
    Check if a string is a valid phone number candidate.
    Must have enough digits, and not just be a year, CTC, or obvious random ID.
    """
    if not text:
        return False
        
    # Remove basic separators
    clean_text = re.sub(r'[\s\-\(\)\+]', '', text)
    if not clean_text.isdigit():
        return False
        
    if len(clean_text) < 8 or len(clean_text) > 15:
        return False
        
    # Check for obvious non-phones (e.g. CTC 10 LPA -> "10") - handled by length constraint
    # Also check if it looks like a date/year like 20261005 (8 chars, but usually context eliminates it)
    return True

def verify_contact(contact: NormalizedContact) -> NormalizedContact:
    # 1. Company Identity
    # 2. Side (Company vs College)
    
    if contact.contact_side == ContactSide.COLLEGE:
        contact.verification_state = PhoneVerificationState.REJECTED_COLLEGE_SIDE
        contact.verification_reason = "Contact belongs to college/institution, not company."
        return contact
        
    # 3. Roles and Context
    low_value_roles = [ContactRole.CUSTOMER_SUPPORT, ContactRole.SALES]
    if contact.contact_role in low_value_roles:
        contact.verification_state = PhoneVerificationState.REJECTED_SUPPORT_OR_SALES
        contact.verification_reason = f"Contact role is {contact.contact_role.value}, not recruitment."
        return contact
        
    if not contact.phone_raw or not is_likely_phone(contact.phone_raw):
        contact.verification_state = PhoneVerificationState.REJECTED_NOT_PHONE
        contact.verification_reason = "Raw phone string is invalid or looks like a non-phone numeric string."
        return contact
        
    # 4. Context missing
    if contact.company_match_confidence == ConfidenceLevel.LOW:
        contact.verification_state = PhoneVerificationState.REJECTED_WRONG_COMPANY
        contact.verification_reason = "Low confidence that contact belongs to the target company."
        return contact
        
    if contact.recruitment_relevance_confidence == ConfidenceLevel.LOW and contact.contact_role not in [
        ContactRole.DIRECT_HR, ContactRole.TALENT_ACQUISITION, ContactRole.CAMPUS_RECRUITMENT,
        ContactRole.UNIVERSITY_RECRUITMENT, ContactRole.RECRUITER, ContactRole.HIRING_MANAGER,
        ContactRole.COMPANY_SWITCHBOARD
    ]:
        contact.verification_state = PhoneVerificationState.REJECTED_WRONG_CONTEXT
        contact.verification_reason = "Low recruitment relevance and not a recognized HR role."
        return contact

    # If it reached here with an actual phone and some context, we can consider it verified
    # The state machine theoretically passes through states. We can just set the terminal state.
    if contact.phone_raw:
        # Determine final state based on confidence
        if contact.recruitment_relevance_confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM]:
            contact.verification_state = PhoneVerificationState.VERIFIED
            contact.verification_reason = "Phone and recruitment context verified."
        elif contact.contact_role == ContactRole.COMPANY_SWITCHBOARD:
            contact.verification_state = PhoneVerificationState.VERIFIED
            contact.verification_reason = "Fallback to company switchboard."
        else:
            contact.verification_state = PhoneVerificationState.UNVERIFIED
            contact.verification_reason = "Insufficient recruitment context to verify."
            
    return contact

def merge_contacts(contacts: List[NormalizedContact]) -> List[NormalizedContact]:
    """
    Deduplicate conservatively.
    Same company + same role + same phone = merge.
    Different phones = don't merge.
    """
    merged = []
    seen = {}
    
    for c in contacts:
        # We only care about terminal states that are valid candidates
        key = f"{c.company_canonical_id}_{c.contact_role}_{c.phone_normalized or c.phone_raw}"
        
        if key not in seen:
            seen[key] = c
            merged.append(c)
        else:
            # For simplicity, keep the one with higher confidence or just the first seen.
            # Real implementation might combine evidence.
            pass
            
    return merged
