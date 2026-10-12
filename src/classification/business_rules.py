from typing import Dict, Any, List
from src.models.domain import NormalizedHiringEvent
from datetime import datetime
import dataclasses

@dataclasses.dataclass
class BusinessClassification:
    role_relevance: str = "UNKNOWN"
    fresher_scope: str = "UNKNOWN"
    package_qualification: str = "UNKNOWN"
    currentness: str = "UNKNOWN"
    campus_mode: str = "UNKNOWN"
    temporal_status: str = "UNKNOWN"
    target_fit: str = "UNKNOWN"
    filter_reasons: List[str] = dataclasses.field(default_factory=list)

def classify_event(event: NormalizedHiringEvent, as_of: datetime = None) -> BusinessClassification:
    if as_of is None:
        as_of = datetime(2026, 10, 5)

    cls = BusinessClassification()
    cls.campus_mode = event.campus_mode or "UNKNOWN"

    # 1. Role Relevance
    tech_roles = [
        "SOFTWARE_ENGINEERING", "AI_ML", "DATA_SCIENCE", "HARDWARE_ENGINEERING", 
        "IT", "SDE", "FULL_STACK", "FULL STACK", "BACKEND", "FRONTEND", "WEB", "MOBILE", 
        "APPLICATION_DEVELOPMENT", "AI", "ML", "GENERATIVE_AI", "LLM", "RAG", 
        "AGENTIC_AI", "NLP", "DATA_ENGINEERING", "DATA_SCIENCE", "DATA ENGINEER", "CLOUD", 
        "DEVOPS", "PLATFORM", "SRE", "CYBERSECURITY", "QA", "TEST_AUTOMATION", 
        "EMBEDDED", "FIRMWARE", "IOT", "NETWORKING", "NETWORK", "SYSTEMS", "DATABASE", 
        "VLSI", "SEMICONDUCTOR_SOFTWARE", "SOLUTIONS_ENGINEERING", "TECHNICAL_SUPPORT", "TECHNICAL SOLUTIONS"
    ]
    non_tech = ["SALES", "MARKETING", "HR", "BPO", "FINANCE", "ADMINISTRATION", "NON_TECH"]
    
    rf = (event.role_family or "").upper()
    role_raw = (event.role_raw or "").upper()
    
    if rf == "UNKNOWN" and not role_raw:
        cls.role_relevance = "UNKNOWN"
    elif rf in tech_roles or any(tr in rf or tr in role_raw for tr in tech_roles):
        cls.role_relevance = "TRUE"
    elif rf in non_tech or any(nt in rf or nt in role_raw for nt in non_tech):
        cls.role_relevance = "FALSE"
    else:
        cls.role_relevance = "UNKNOWN"

    # 2. Fresher Scope
    if event.graduation_year:
        if event.graduation_year in [2026, 2027]:
            cls.fresher_scope = "TRUE"
        else:
            cls.fresher_scope = "FALSE"
    elif event.batch_raw:
        b_raw = event.batch_raw.upper()
        if "2026" in b_raw or "2027" in b_raw:
            cls.fresher_scope = "TRUE"
        elif "2024" in b_raw or "2025" in b_raw:
            cls.fresher_scope = "FALSE"
        else:
            cls.fresher_scope = "UNKNOWN"
    else:
        cls.fresher_scope = "UNKNOWN"

    # 3. Package Qualification
    ctc = event.ctc
    branches = [b.upper() for b in (event.eligible_branches or [])]
    
    has_cse = "CSE" in branches or "COMPUTER SCIENCE" in branches or "IT" in branches or "ALL_BRANCHES" in branches
    has_ece = "ECE" in branches or "ELECTRONICS" in branches or "ALL_BRANCHES" in branches
    
    if ctc is None:
        cls.package_qualification = "UNKNOWN"
    else:
        qualified_cse = has_cse and ctc >= 10.0
        qualified_ece = has_ece and ctc >= 6.5
        
        if not branches:
            cls.package_qualification = "UNKNOWN"
        elif qualified_cse and qualified_ece:
            cls.package_qualification = "QUALIFIED_CSE_AND_ECE"
        elif qualified_cse:
            cls.package_qualification = "QUALIFIED_CSE"
        elif qualified_ece:
            cls.package_qualification = "QUALIFIED_ECE"
        else:
            cls.package_qualification = "NOT_QUALIFIED"

    # 4. Currentness & Temporal Status
    edate = None
    if event.event_date:
        try:
            edate = datetime.strptime(event.event_date, "%Y-%m-%d")
        except ValueError:
            pass

    rdate = None
    if event.registration_deadline:
        try:
            rdate = datetime.strptime(event.registration_deadline, "%Y-%m-%d")
        except ValueError:
            pass

    if edate:
        delta = (as_of - edate).days
        if delta < 0:
            cls.currentness = "UPCOMING"
            cls.temporal_status = "ACTIVE_OPPORTUNITY"
        elif delta == 0:
            cls.currentness = "ONGOING"
            cls.temporal_status = "ACTIVE_OPPORTUNITY"
        elif 0 < delta <= 15:
            cls.currentness = "COMPLETED_RECENT"
            cls.temporal_status = "HOT_OUTREACH_LEAD"
        else:
            cls.currentness = "COMPLETED_OUTSIDE_15_DAY_WINDOW"
            cls.temporal_status = "STALE"
    elif rdate:
        delta = (as_of - rdate).days
        if delta <= 0:
            cls.currentness = "REGISTRATION_OPEN"
            cls.temporal_status = "ACTIVE_OPPORTUNITY"
        else:
            cls.currentness = "UNKNOWN"
            cls.temporal_status = "UNKNOWN"
    else:
        cls.currentness = "UNKNOWN"
        cls.temporal_status = "UNKNOWN"

    # 5. Target Fit (Actionability)
    if cls.temporal_status == "STALE":
        cls.target_fit = "FILTERED_OUT"
        cls.filter_reasons.append("Stale event (>15 days old)")
    elif cls.role_relevance == "FALSE":
        cls.target_fit = "FILTERED_OUT"
        cls.filter_reasons.append("Non-tech role")
    elif cls.fresher_scope == "FALSE":
        cls.target_fit = "FILTERED_OUT"
        cls.filter_reasons.append("Outside fresher batch scope")
    elif cls.package_qualification == "NOT_QUALIFIED":
        cls.target_fit = "FILTERED_OUT"
        cls.filter_reasons.append("Does not meet CTC branch threshold")
    else:
        if cls.role_relevance == "UNKNOWN" or cls.fresher_scope == "UNKNOWN" or cls.package_qualification == "UNKNOWN":
            cls.target_fit = "REVIEW"
            if cls.role_relevance == "UNKNOWN":
                cls.filter_reasons.append("Role relevance unknown")
            if cls.fresher_scope == "UNKNOWN":
                cls.filter_reasons.append("Fresher scope unknown")
            if cls.package_qualification == "UNKNOWN":
                cls.filter_reasons.append("Package qualification unknown")
        else:
            cls.target_fit = "QUALIFIED"

    return cls

def apply_business_filters(events: List[NormalizedHiringEvent], as_of: datetime = None) -> Dict[str, Any]:
    event_classes = {}
    for ev in events:
        classification = classify_event(ev, as_of)
        ev.status_normalized = classification.temporal_status
        event_classes[ev.event_id] = classification
        
    return {"classifications": event_classes}
