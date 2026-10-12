from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import relationship
from .outreach import Base
from .json_type import JSONEncodedDict

class SystemAlert(Base):
    __tablename__ = "system_alerts"

    id = Column(String, primary_key=True)
    snapshot_id = Column(String, ForeignKey("snapshots.snapshot_id"), nullable=True)
    lead_id = Column(String, ForeignKey("outreach_leads.canonical_event_id"), nullable=True, index=True)
    
    alert_type = Column(String, nullable=False) # e.g. 'NEW_LEAD', 'CTC_CHANGED'
    priority = Column(String, nullable=False)   # 'URGENT', 'ACTION_REQUIRED', 'INFORMATIONAL', 'SYSTEM_WARNING'
    
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    
    old_value = Column(JSONEncodedDict, nullable=True)
    new_value = Column(JSONEncodedDict, nullable=True)
    evidence_reference = Column(JSONEncodedDict, nullable=True)
    
    change_fingerprint = Column(String, nullable=False)
    
    status = Column(String, nullable=False, default="NEW") # 'NEW', 'ACKNOWLEDGED', 'ACTIONED', 'DISMISSED', 'EXPIRED'
    
    delivery_status = Column(String, nullable=False, default="PENDING") # 'PENDING', 'SENT', 'FAILED', 'RETRYABLE', 'EXHAUSTED'
    delivery_attempts = Column(Integer, nullable=False, default=0)
    
    detected_at = Column(DateTime, nullable=False, default=func.now())
    created_at = Column(DateTime, nullable=False, default=func.now())
    acknowledged_at = Column(DateTime, nullable=True)
    actioned_at = Column(DateTime, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint('change_fingerprint', name='uq_alert_change_fingerprint'),
        Index('ix_alerts_status', 'status'),
        Index('ix_alerts_priority', 'priority'),
        Index('ix_alerts_delivery', 'delivery_status'),
    )

    snapshot = relationship("SnapshotMetadata", backref="alerts")
    lead = relationship("OutreachLead", backref="alerts")
