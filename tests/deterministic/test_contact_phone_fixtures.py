import pytest
from src.extraction.contact_extractor import map_role_from_text, map_side_from_role
from src.models.contact import ContactRole, ContactSide, PhoneVerificationState, NormalizedContact
from src.verification.contact_verifier import verify_contact

def test_contact_taxonomy():
    # Test valid recruitment roles
    assert map_role_from_text("Senior HR Manager") == ContactRole.DIRECT_HR
    assert map_role_from_text("VP of Talent Acquisition") == ContactRole.TALENT_ACQUISITION
    assert map_role_from_text("Campus Recruitment Lead") == ContactRole.CAMPUS_RECRUITMENT
    assert map_role_from_text("University Recruitment") == ContactRole.CAMPUS_RECRUITMENT
    assert map_role_from_text("Technical Recruiter") == ContactRole.RECRUITER
    
    # Test invalid / non-recruitment roles
    assert map_role_from_text("College Placement Officer") == ContactRole.COLLEGE_CONTACT
    assert map_role_from_text("Customer Support Helpdesk") == ContactRole.CUSTOMER_SUPPORT
    assert map_role_from_text("Sales Director") == ContactRole.SALES
    
    # Test sides
    assert map_side_from_role(ContactRole.COLLEGE_CONTACT) == ContactSide.COLLEGE
    assert map_side_from_role(ContactRole.DIRECT_HR) == ContactSide.COMPANY
    assert map_side_from_role(ContactRole.SALES) == ContactSide.COMPANY

def test_phone_state_machine_valid():
    from src.models.contact import ConfidenceLevel, ContactRole, ContactSide, PhoneVerificationState, NormalizedContact
    from src.verification.contact_verifier import verify_contact
    
    from datetime import datetime
    base = {
        "company_canonical_id": "cmp1",
        "company_name": "Test Company",
        "source_url": "http://test",
        "source_type": "PDF",
        "evidence_text": "contact",
        "evidence_location": "footer",
        "retrieved_at": datetime(2026, 10, 5).isoformat()
    }

    # Negative: College contact
    contact_college = NormalizedContact(
        contact_id="c1", phone_raw="+91 9876543210", 
        contact_role=ContactRole.COLLEGE_CONTACT, contact_side=ContactSide.COLLEGE,
        **base
    )
    res = verify_contact(contact_college)
    assert res.verification_state == PhoneVerificationState.REJECTED_COLLEGE_SIDE
    
    # Negative: Customer Support
    contact_support = NormalizedContact(
        contact_id="c2", phone_raw="1800 123 4567",
        contact_role=ContactRole.CUSTOMER_SUPPORT, contact_side=ContactSide.COMPANY,
        **base
    )
    res = verify_contact(contact_support)
    assert res.verification_state == PhoneVerificationState.REJECTED_SUPPORT_OR_SALES
    
    # Negative: Low context / Unknown
    contact_unknown = NormalizedContact(
        contact_id="c3", phone_raw="1234567890",
        contact_role=ContactRole.UNKNOWN, contact_side=ContactSide.COMPANY,
        company_match_confidence=ConfidenceLevel.HIGH,
        recruitment_relevance_confidence=ConfidenceLevel.LOW,
        **base
    )
    res = verify_contact(contact_unknown)
    assert res.verification_state == PhoneVerificationState.REJECTED_WRONG_CONTEXT
    
    # Positive: Verified recruitment
    contact_hr = NormalizedContact(
        contact_id="c4", phone_raw="+91 9876543210",
        contact_role=ContactRole.DIRECT_HR, contact_side=ContactSide.COMPANY,
        company_match_confidence=ConfidenceLevel.HIGH,
        recruitment_relevance_confidence=ConfidenceLevel.HIGH,
        **base
    )
    res = verify_contact(contact_hr)
    assert res.verification_state == PhoneVerificationState.VERIFIED
