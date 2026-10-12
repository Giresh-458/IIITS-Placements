from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CrawlRun(BaseModel):
    run_id: str
    source_id: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    urls_attempted: int = 0
    urls_successful: int = 0
    urls_failed: int = 0
    pages_fetched: int = 0
    browser_pages: int = 0
    http_requests: int = 0
    pdfs_processed: int = 0
    events_discovered: int = 0
    events_validated: int = 0
    contacts_discovered: int = 0
    phones_discovered: int = 0
    phones_verified: int = 0
    retries: int = 0
    exceptions: int = 0
    stop_reason: Optional[str] = None

class TelemetryRecord(BaseModel):
    record_id: str
    run_id: str
    timestamp: datetime
    event_type: str
    message: str
    metadata: dict = {}
