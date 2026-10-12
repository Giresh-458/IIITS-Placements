from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Boolean, DateTime, Text
from src.storage.models.json_type import JSONEncodedDict as JSON
from datetime import datetime
import enum
from typing import Optional, List, Dict, Any

class Base(DeclarativeBase):
    pass

class OperationalStatus(str, enum.Enum):
    NEW = "NEW"
    REVIEWED = "REVIEWED"
    READY_FOR_OUTREACH = "READY_FOR_OUTREACH"
    OUTREACH_ATTEMPTED = "OUTREACH_ATTEMPTED"
    CONTACTED = "CONTACTED"
    RESPONDED = "RESPONDED"
    FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"
    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    DO_NOT_PURSUE = "DO_NOT_PURSUE"
    CLOSED = "CLOSED"

class SnapshotMetadata(Base):
    __tablename__ = "snapshots"
    snapshot_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_artifact: Mapped[str] = mapped_column(String)
    source_hash: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    record_count: Mapped[int] = mapped_column(Integer)
    ingestion_status: Mapped[str] = mapped_column(String) # SUCCESS, REJECTED

class OutreachLead(Base):
    __tablename__ = "outreach_leads"
    
    # Source truth
    canonical_event_id: Mapped[str] = mapped_column(String, primary_key=True)
    company_name: Mapped[Optional[str]] = mapped_column(String, index=True)
    role: Mapped[Optional[str]] = mapped_column(String)
    batch: Mapped[Optional[str]] = mapped_column(String)
    branches: Mapped[Optional[str]] = mapped_column(String) # e.g. ["CSE", "ECE"]
    ctc: Mapped[Optional[str]] = mapped_column(String)
    event_date: Mapped[Optional[str]] = mapped_column(String, index=True)
    registration_deadline: Mapped[Optional[str]] = mapped_column(String)
    
    role_relevance: Mapped[Optional[str]] = mapped_column(String)
    fresher_scope: Mapped[Optional[str]] = mapped_column(String)
    branch_qualification: Mapped[Optional[str]] = mapped_column(String)
    package_qualification: Mapped[Optional[str]] = mapped_column(String)
    target_fit: Mapped[Optional[str]] = mapped_column(String)
    temporal_status: Mapped[Optional[str]] = mapped_column(String)
    
    outreach_priority: Mapped[str] = mapped_column(String, index=True)
    outreach_readiness: Mapped[str] = mapped_column(String)
    contact_status: Mapped[str] = mapped_column(String)
    verified_contact_ids: Mapped[Optional[str]] = mapped_column(String)
    
    priority_reason: Mapped[Optional[str]] = mapped_column(String)
    readiness_reason: Mapped[Optional[str]] = mapped_column(String)
    
    source_lineage: Mapped[Optional[str]] = mapped_column(String)
    
    # Snapshot reference
    snapshot_id: Mapped[str] = mapped_column(String)
    
    # Operational fields (mutated by workflow)
    outreach_status: Mapped[str] = mapped_column(String, default=OperationalStatus.NEW.value, index=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String)
    follow_up_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    outreach_notes: Mapped[Optional[str]] = mapped_column(Text)
    last_contact_attempt: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Audit tracking
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Soft deletion/history tracking for snapshot changes
    currently_present: Mapped[bool] = mapped_column(Boolean, default=True)

class OutreachContact(Base):
    __tablename__ = "outreach_contacts"
    contact_id: Mapped[str] = mapped_column(String, primary_key=True)
    company: Mapped[str] = mapped_column(String, index=True)
    person_name: Mapped[Optional[str]] = mapped_column(String)
    contact_role: Mapped[Optional[str]] = mapped_column(String)
    phone: Mapped[Optional[str]] = mapped_column(String)
    verification_state: Mapped[str] = mapped_column(String)
    confidence: Mapped[str] = mapped_column(String)
    linked_event_ids: Mapped[Optional[str]] = mapped_column(String)
    evidence: Mapped[Optional[str]] = mapped_column(String)
    
    snapshot_id: Mapped[str] = mapped_column(String)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    entity_type: Mapped[str] = mapped_column(String) # LEAD, CONTACT, SNAPSHOT
    entity_id: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    previous_state: Mapped[Optional[str]] = mapped_column(String)
    new_state: Mapped[Optional[str]] = mapped_column(String)
    reason: Mapped[Optional[str]] = mapped_column(String)
