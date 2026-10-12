from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime, date

from .enums import (
    CampusEventType,
    EventStatus,
    RoleCategory,
    ContactRole,
    SourceAccessClassification,
    SourceIntendedRole,
    InstitutionType
)

class College(BaseModel):
    id: Optional[str] = None
    name: str
    institution_type: InstitutionType
    domain: Optional[str] = None
    is_target_profile: bool = False

class SourceNode(BaseModel):
    source_id: str
    parent_source_id: Optional[str] = None
    url: str
    depth: int = 0
    page_type: str = "UNKNOWN"
    access_status: SourceAccessClassification = SourceAccessClassification.NOT_VERIFIED
    http_status: Optional[int] = None
    redirect_chain: List[str] = Field(default_factory=list)
    is_public: bool = False
    is_auth_wall: bool = False
    is_event_index: bool = False
    is_event_record: bool = False
    is_archive: bool = False
    is_notice: bool = False
    is_pdf: bool = False
    is_api: bool = False
    crawl_timestamp: datetime = Field(default_factory=datetime.utcnow)

class CapabilityEvidence(BaseModel):
    capability: str
    value: str  # "TRUE", "FALSE", "UNKNOWN"
    source_url: Optional[str] = None
    evidence_url: Optional[str] = None
    evidence_text: Optional[str] = None
    evidence_location: Optional[str] = None
    extraction_method: Optional[str] = None
    confidence: float = 0.0
    
    # Event specific fields
    event_title: Optional[str] = None
    company_name_if_available: Optional[str] = None
    event_url: Optional[str] = None
    event_date_if_available: Optional[str] = None
    event_date_confidence: Optional[str] = None
    publication_date: Optional[str] = None
    last_modified_date: Optional[str] = None
    registration_deadline_if_available: Optional[str] = None
    role_if_available: Optional[str] = None
    branch_if_available: Optional[str] = None
    batch_if_available: Optional[str] = None
    ctc_if_available: Optional[str] = None
    campus_mode_if_available: Optional[str] = None
    evidence_excerpt: Optional[str] = None

class SourceCapabilities(BaseModel):
    event_discovery: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="event_discovery", value="UNKNOWN"))
    has_company: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_company", value="UNKNOWN"))
    has_role: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_role", value="UNKNOWN"))
    has_event_date: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_event_date", value="UNKNOWN"))
    has_registration_deadline: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_registration_deadline", value="UNKNOWN"))
    has_eligible_branches: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_eligible_branches", value="UNKNOWN"))
    has_batch: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_batch", value="UNKNOWN"))
    has_cgpa: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_cgpa", value="UNKNOWN"))
    has_ctc: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_ctc", value="UNKNOWN"))
    has_salary: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_salary", value="UNKNOWN"))
    has_location: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_location", value="UNKNOWN"))
    has_selection_process: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_selection_process", value="UNKNOWN"))
    has_contact_name: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_contact_name", value="UNKNOWN"))
    has_contact_phone: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_contact_phone", value="UNKNOWN"))
    has_contact_email: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_contact_email", value="UNKNOWN"))
    has_event_status: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_event_status", value="UNKNOWN"))
    has_pdf_links: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_pdf_links", value="UNKNOWN"))
    has_archive: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_archive", value="UNKNOWN"))
    has_pagination: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_pagination", value="UNKNOWN"))
    has_individual_event_pages: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_individual_event_pages", value="UNKNOWN"))
    has_recent_event_data: CapabilityEvidence = Field(default_factory=lambda: CapabilityEvidence(capability="has_recent_event_data", value="UNKNOWN"))

class SourceQualityScore(BaseModel):
    public_access_score: float = 0.0
    event_detail_score: float = 0.0
    freshness_score: float = 0.0
    cse_ece_relevance_score: float = 0.0
    structuredness_score: float = 0.0
    contact_value_score: float = 0.0
    stability_score: float = 0.0
    
    @property
    def total_score(self) -> float:
        return (
            self.public_access_score + self.event_detail_score + self.freshness_score +
            self.cse_ece_relevance_score + self.structuredness_score + self.contact_value_score +
            self.stability_score
        )

class SourceProfile(BaseModel):
    access_status: SourceAccessClassification = SourceAccessClassification.NOT_VERIFIED
    intended_roles: List[SourceIntendedRole] = Field(default_factory=list)
    crawl_method: Optional[str] = None
    requires_browser: bool = False
    parser_type: Optional[str] = None
    max_pages: Optional[int] = None
    capabilities: SourceCapabilities = Field(default_factory=SourceCapabilities)
    quality_score: SourceQualityScore = Field(default_factory=SourceQualityScore)
    notes: Optional[str] = None

class Source(BaseModel):
    id: Optional[str] = None
    college_id: Optional[str] = None
    url: str
    canonical_url: Optional[str] = None
    priority: int = 0
    status: str = "UNVERIFIED"
    profile: SourceProfile = Field(default_factory=SourceProfile)
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None

class SourceVerificationEvidence(BaseModel):
    source_id: Optional[str] = None
    verification_timestamp: datetime
    verification_method: str
    final_url: str
    http_status: Optional[int] = None
    access_status: SourceAccessClassification
    observed_page_title: Optional[str] = None
    observed_content_summary: Optional[str] = None
    observed_capabilities: SourceCapabilities
    login_detected: bool = False
    browser_required: bool = False
    evidence_snippets: List[str] = Field(default_factory=list)
    linked_documents: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

class Evidence(BaseModel):
    id: Optional[str] = None
    source_url: str
    source_type: SourceAccessClassification
    retrieved_at: datetime
    evidence_text: Optional[str] = None
    content_location: Optional[str] = None
    page_number: Optional[int] = None
    content_hash: Optional[str] = None
    extraction_method: Optional[str] = None
    confidence: float = 0.0
    validation_status: Optional[str] = None

class Company(BaseModel):
    id: Optional[str] = None
    name: str
    website: Optional[str] = None
    industry: Optional[str] = None

class Job(BaseModel):
    id: Optional[str] = None
    company_id: Optional[str] = None
    title: Optional[str] = None
    role_categories: List[RoleCategory] = Field(default_factory=list)
    ctc_lpa: Optional[float] = None
    eligible_branches: List[str] = Field(default_factory=list)
    eligible_batch: Optional[str] = None
    cgpa_threshold: Optional[float] = None

class HiringEvent(BaseModel):
    id: Optional[str] = None
    college_id: Optional[str] = None
    company_id: Optional[str] = None
    campus_type: CampusEventType = CampusEventType.UNKNOWN
    event_date: Optional[date] = None
    registration_deadline: Optional[datetime] = None
    event_status: EventStatus = EventStatus.UNKNOWN
    jobs: List[Job] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    first_seen: Optional[datetime] = None
    last_verified: Optional[datetime] = None

class HiringEventCandidate(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    institution: str
    company_name: Optional[str] = None
    event_title: Optional[str] = None
    event_url: Optional[str] = None
    source_seed_url: str
    role: Optional[str] = None
    eligible_branches: List[str] = Field(default_factory=list)
    batch: Optional[str] = None
    graduation_year: Optional[int] = None
    ctc: Optional[float] = None
    ctc_raw: Optional[str] = None
    cgpa_requirement: Optional[float] = None
    event_date: Optional[datetime] = None
    event_date_raw: Optional[str] = None
    event_date_confidence: Optional[str] = None
    registration_deadline: Optional[datetime] = None
    registration_deadline_raw: Optional[str] = None
    campus_mode: Optional[str] = None
    event_status: str = "UNKNOWN_STATUS"
    is_recent: bool = False
    raw_text_excerpt: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    source_metadata: Dict[str, Any] = Field(default_factory=dict)
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    confidence_fields: Dict[str, str] = Field(default_factory=dict)

class PhoneCandidate(BaseModel):
    raw_number: str
    normalized_number: Optional[str] = None
    is_verified: bool = False
    verification_method: Optional[str] = None

class NormalizedHiringEvent(BaseModel):
    event_id: str
    source_event_id: Optional[str] = None
    event_status: str = "UNKNOWN_STATUS"
    institution: str
    institution_id: Optional[str] = None
    source_seed_id: Optional[str] = None
    company_name: Optional[str] = None
    company_name_raw: Optional[str] = None
    company_aliases: List[str] = Field(default_factory=list)
    event_title: Optional[str] = None
    event_title_raw: Optional[str] = None
    role: Optional[str] = None
    role_raw: Optional[str] = None
    role_family: str = "UNKNOWN"
    role_subtype: Optional[str] = None
    eligible_branches: List[str] = Field(default_factory=list)
    eligible_branches_raw: Optional[str] = None
    branch_groups: List[str] = Field(default_factory=list)
    batch: Optional[str] = None
    batch_raw: Optional[str] = None
    graduation_year: Optional[int] = None
    ctc: Optional[float] = None
    ctc_raw: Optional[str] = None
    ctc_currency: Optional[str] = None
    ctc_unit: Optional[str] = None
    ctc_period: Optional[str] = None
    cgpa_requirement: Optional[float] = None
    cgpa_raw: Optional[str] = None
    event_date: Optional[str] = None
    event_date_raw: Optional[str] = None
    event_date_confidence: str = "UNKNOWN"
    registration_deadline: Optional[str] = None
    registration_deadline_raw: Optional[str] = None
    registration_deadline_confidence: str = "UNKNOWN"
    publication_date: Optional[str] = None
    publication_date_raw: Optional[str] = None
    last_modified_date: Optional[str] = None
    last_modified_date_raw: Optional[str] = None
    campus_mode: str = "UNKNOWN"
    campus_mode_raw: Optional[str] = None
    event_type: str = "UNKNOWN"
    event_type_raw: Optional[str] = None
    location: Optional[str] = None
    location_raw: Optional[str] = None
    eligibility_text: Optional[str] = None
    selection_process: List[str] = Field(default_factory=list)
    selection_process_raw: Optional[str] = None
    status_raw: Optional[str] = None
    status_normalized: str = "UNKNOWN"
    is_recent: bool = False
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    field_confidence: Dict[str, str] = Field(default_factory=dict)
    normalization_warnings: List[str] = Field(default_factory=list)
    extraction_warnings: List[str] = Field(default_factory=list)
    canonical_identity: Optional[str] = None
    discovered_at: Optional[str] = None
    normalized_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    source_urls: List[str] = Field(default_factory=list)
    source_seed_url: Optional[str] = None
    event_url: Optional[str] = None
    raw_event_text: Optional[str] = None

class Person(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phones: List[PhoneCandidate] = Field(default_factory=list)
    linkedin_url: Optional[str] = None

class Contact(BaseModel):
    id: Optional[str] = None
    person_id: Optional[str] = None
    company_id: Optional[str] = None
    role: ContactRole = ContactRole.UNKNOWN
    evidence_ids: List[str] = Field(default_factory=list)
