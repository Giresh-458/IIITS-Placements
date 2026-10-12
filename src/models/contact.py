from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class ContactSide(str, Enum):
    COMPANY = "COMPANY"
    COLLEGE = "COLLEGE"
    UNKNOWN = "UNKNOWN"

class ContactRole(str, Enum):
    DIRECT_HR = "DIRECT_HR"
    TALENT_ACQUISITION = "TALENT_ACQUISITION"
    CAMPUS_RECRUITMENT = "CAMPUS_RECRUITMENT"
    UNIVERSITY_RECRUITMENT = "UNIVERSITY_RECRUITMENT"
    RECRUITER = "RECRUITER"
    HIRING_MANAGER = "HIRING_MANAGER"
    RECRUITMENT_AGENCY = "RECRUITMENT_AGENCY"
    HR_HELPDESK = "HR_HELPDESK"
    COMPANY_SWITCHBOARD = "COMPANY_SWITCHBOARD"
    CUSTOMER_SUPPORT = "CUSTOMER_SUPPORT"
    SALES = "SALES"
    COLLEGE_CONTACT = "COLLEGE_CONTACT"
    UNKNOWN = "UNKNOWN"

class PhoneVerificationState(str, Enum):
    PHONE_DISCOVERED = "PHONE_DISCOVERED"
    PHONE_CONTEXT_FOUND = "PHONE_CONTEXT_FOUND"
    COMPANY_MATCHED = "COMPANY_MATCHED"
    PERSON_MATCHED = "PERSON_MATCHED"
    RECRUITMENT_RELEVANCE_CONFIRMED = "RECRUITMENT_RELEVANCE_CONFIRMED"
    ROLE_RELEVANCE_CONFIRMED = "ROLE_RELEVANCE_CONFIRMED"
    CROSS_SOURCE_CONFIRMED = "CROSS_SOURCE_CONFIRMED"
    CURRENTNESS_CONFIRMED = "CURRENTNESS_CONFIRMED"
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    REJECTED_WRONG_COMPANY = "REJECTED_WRONG_COMPANY"
    REJECTED_WRONG_CONTEXT = "REJECTED_WRONG_CONTEXT"
    REJECTED_NOT_PHONE = "REJECTED_NOT_PHONE"
    REJECTED_COLLEGE_SIDE = "REJECTED_COLLEGE_SIDE"
    REJECTED_SUPPORT_OR_SALES = "REJECTED_SUPPORT_OR_SALES"
    NO_VERIFIED_PUBLIC_RECRUITMENT_PHONE = "NO_VERIFIED_PUBLIC_RECRUITMENT_PHONE"
    CONTACT_DISCOVERY_INCOMPLETE = "CONTACT_DISCOVERY_INCOMPLETE"
    COMPANY_IDENTITY_REQUIRED = "COMPANY_IDENTITY_REQUIRED"

class ContactCurrentness(str, Enum):
    CURRENTNESS_CONFIRMED = "CURRENTNESS_CONFIRMED"
    CURRENTNESS_PLAUSIBLE = "CURRENTNESS_PLAUSIBLE"
    CURRENTNESS_UNKNOWN = "CURRENTNESS_UNKNOWN"
    STALE_SUSPECTED = "STALE_SUSPECTED"

class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"

class NormalizedContact(BaseModel):
    contact_id: str
    company_canonical_id: str
    company_name: str
    person_name: Optional[str] = None
    contact_role: ContactRole = ContactRole.UNKNOWN
    contact_side: ContactSide = ContactSide.UNKNOWN
    department: Optional[str] = None
    phone_raw: Optional[str] = None
    phone_normalized: Optional[str] = None
    phone_country: Optional[str] = None
    email_raw: Optional[str] = None
    email_normalized: Optional[str] = None
    source_url: str
    source_type: str
    source_title: Optional[str] = None
    evidence_text: str
    evidence_location: str
    retrieved_at: str
    
    company_match_confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    person_match_confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    contact_role_confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    recruitment_relevance_confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    role_relevance_confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    phone_confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    currentness_confidence: ContactCurrentness = ContactCurrentness.CURRENTNESS_UNKNOWN
    
    verification_state: PhoneVerificationState = PhoneVerificationState.PHONE_DISCOVERED
    verification_reason: Optional[str] = None
