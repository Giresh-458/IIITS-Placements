from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime

class CrawlTelemetry(BaseModel):
    run_id: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    sources_attempted: int = 0
    sources_succeeded: int = 0
    sources_failed: int = 0
    
    pages_attempted: int = 0
    pages_succeeded: int = 0
    pages_failed: int = 0
    
    requests_attempted: int = 0
    requests_succeeded: int = 0
    requests_failed: int = 0
    
    http_requests: int = 0
    browser_pages: int = 0
    browser_escalations: int = 0
    browser_failures: int = 0
    
    timeouts: int = 0
    retries: int = 0
    pdfs_found: int = 0
    pdfs_processed: int = 0
    
    event_candidates_found: int = 0
    events_normalized: int = 0
    events_deduplicated: int = 0
    events_recent: int = 0
    events_upcoming: int = 0
    events_completed_15d: int = 0
    events_older: int = 0
    
    authentication_blocks: int = 0
    forbidden_blocks: int = 0
    
    exceptions: List[Dict] = Field(default_factory=list)
    stop_reason: Optional[str] = None
    
    source_stats: Dict[str, Dict] = Field(default_factory=dict)
