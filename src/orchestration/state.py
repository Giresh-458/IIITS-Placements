import os
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime

class RunTelemetry(TypedDict):
    run_id: str
    started_at: Optional[str]
    completed_at: Optional[str]
    total_duration_seconds: float
    sources_attempted: int
    sources_succeeded: int
    sources_failed: int
    urls_fetched: int
    http_requests: int
    browser_pages: int
    pdfs: int
    retries: int
    extraction_candidates: int
    normalized_events: int
    qualified_events: int
    rejected_events: int
    consolidated_leads: int
    contacts_discovered: int
    phones_discovered: int
    verified_phones: int
    persistence_inserts: int
    persistence_updates: int
    persistence_unchanged: int
    alerts_generated: int
    alerts_deduplicated: int
    exceptions: int
    terminal_status: str
    stop_reason: Optional[str]

class PipelineRunState(TypedDict):
    run_id: str
    started_at: str
    completed_at: Optional[str]
    current_stage: str
    
    # Discovery & Crawl
    sources: List[Dict[str, Any]]
    sources_override_provided: bool
    failed_sources: List[Dict[str, Any]]
    crawl_telemetry: Dict[str, Any]
    
    # Extraction & Normalization
    raw_candidates: List[Dict[str, Any]]
    normalized_events: List[Dict[str, Any]]
    
    # Qualification
    qualified_events: List[Dict[str, Any]]
    rejected_events: List[Dict[str, Any]]
    
    # Evidence & Entities
    evidence: List[Dict[str, Any]]
    companies: List[Dict[str, Any]]
    
    # Contacts
    contacts: List[Dict[str, Any]]
    phones: List[Dict[str, Any]]
    verified_phones: List[Dict[str, Any]]
    
    # Consolidation
    consolidated_leads: List[Dict[str, Any]]
    
    # Persistence
    snapshot_id: Optional[str]
    persistence_result: Optional[Dict[str, Any]]
    alert_result: Optional[List[Dict[str, Any]]]
    
    # Overall Status
    errors: List[Dict[str, Any]]
    warnings: List[str]
    telemetry: RunTelemetry
    terminal_status: str
    stop_reason: Optional[str]

def create_initial_state(run_id: str = None, sources: List[Dict[str, Any]] = None) -> PipelineRunState:
    import uuid
    if not run_id:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
    
    return {
        "run_id": run_id,
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "current_stage": "INITIALIZED",
        "sources": list(sources) if sources is not None else [],
        "sources_override_provided": sources is not None,
        "failed_sources": [],
        "crawl_telemetry": {},
        "raw_candidates": [],
        "normalized_events": [],
        "qualified_events": [],
        "rejected_events": [],
        "evidence": [],
        "companies": [],
        "contacts": [],
        "phones": [],
        "verified_phones": [],
        "consolidated_leads": [],
        "snapshot_id": None,
        "persistence_result": None,
        "alert_result": None,
        "errors": [],
        "warnings": [],
        "telemetry": {
            "run_id": run_id,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "total_duration_seconds": 0.0,
            "sources_attempted": 0,
            "sources_succeeded": 0,
            "sources_failed": 0,
            "urls_fetched": 0,
            "http_requests": 0,
            "browser_pages": 0,
            "pdfs": 0,
            "retries": 0,
            "extraction_candidates": 0,
            "normalized_events": 0,
            "qualified_events": 0,
            "rejected_events": 0,
            "consolidated_leads": 0,
            "contacts_discovered": 0,
            "phones_discovered": 0,
            "verified_phones": 0,
            "persistence_inserts": 0,
            "persistence_updates": 0,
            "persistence_unchanged": 0,
            "alerts_generated": 0,
            "alerts_deduplicated": 0,
            "exceptions": 0,
            "terminal_status": "RUNNING",
            "stop_reason": None
        },
        "terminal_status": "RUNNING",
        "stop_reason": None
    }
