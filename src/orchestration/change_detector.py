import json
import hashlib
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.models.outreach import OutreachLead, OutreachContact
from src.storage.models.alerts import SystemAlert
from sqlalchemy import select

class ChangeDetector:
    def __init__(self, session: AsyncSession, snapshot_id: str):
        self.session = session
        self.snapshot_id = snapshot_id

    def generate_fingerprint(self, lead_id: str, alert_type: str, old_val: Any, new_val: Any) -> str:
        if alert_type in ("SNAPSHOT_INGESTED", "SNAPSHOT_FAILED", "SOURCE_HEALTH_DEGRADED"):
            import uuid
            s = f"{self.snapshot_id}_{alert_type}_{uuid.uuid4().hex}"
        else:
            s = f"{self.snapshot_id}_{lead_id}_{alert_type}_{json.dumps(old_val)}_{json.dumps(new_val)}"
        return hashlib.sha256(s.encode('utf-8')).hexdigest()

    async def _create_alert(self, lead_id: str, alert_type: str, priority: str, title: str, message: str, old_val: Any = None, new_val: Any = None, evidence: Any = None):
        fingerprint = self.generate_fingerprint(lead_id, alert_type, old_val, new_val)
        
        # Check if exists in session or db
        existing = await self.session.execute(select(SystemAlert).where(SystemAlert.change_fingerprint == fingerprint))
        if existing.scalars().first():
            return None # Suppress duplicate
        
        # Generate alert ID
        import uuid
        alert_id = f"alrt_{uuid.uuid4().hex[:12]}"
        
        alert = SystemAlert(
            id=alert_id,
            snapshot_id=self.snapshot_id,
            lead_id=lead_id,
            alert_type=alert_type,
            priority=priority,
            title=title,
            message=message,
            old_value=old_val,
            new_value=new_val,
            evidence_reference=evidence,
            change_fingerprint=fingerprint,
            status="NEW",
            delivery_status="PENDING"
        )
        self.session.add(alert)
        return alert

    async def detect_changes_for_lead(self, new_data: dict, old_lead: OutreachLead):
        cid = new_data["canonical_event_id"]
        company = new_data.get("company_name", "Unknown")
        
        alerts_generated = []
        
        # 1. Status Changes
        old_status = old_lead.temporal_status
        new_status = new_data.get("temporal_status")
        if old_status != new_status:
            alrt = await self._create_alert(cid, "STATUS_CHANGED", "INFORMATIONAL", f"Status Changed: {company}", f"Status changed from {old_status} to {new_status}.", old_val=old_status, new_val=new_status)
            if alrt: alerts_generated.append(alrt)
            if new_status == "HOT_OUTREACH_LEAD":
                alrt = await self._create_alert(cid, "HOT_OUTREACH_LEAD_ENTERED", "ACTION_REQUIRED", f"Hot Lead: {company}", f"{company} is now a HOT outreach lead.", old_val=old_status, new_val=new_status)
                if alrt: alerts_generated.append(alrt)
            elif new_status == "ACTIVE_OPPORTUNITY":
                alrt = await self._create_alert(cid, "ACTIVE_OPPORTUNITY_ENTERED", "INFORMATIONAL", f"Active Opp: {company}", f"{company} is now an ACTIVE opportunity.", old_val=old_status, new_val=new_status)
                if alrt: alerts_generated.append(alrt)

        # 2. Priority Changed
        old_priority = old_lead.outreach_priority
        new_priority = new_data.get("outreach_priority")
        if old_priority != new_priority:
            alrt = await self._create_alert(cid, "PRIORITY_CHANGED", "INFORMATIONAL", f"Priority Changed: {company}", f"Priority changed from {old_priority} to {new_priority}.", old_val=old_priority, new_val=new_priority)
            if alrt: alerts_generated.append(alrt)

        # 3. Event Date Changed
        old_event_date = str(old_lead.event_date) if old_lead.event_date else None
        new_event_date = str(new_data.get("event_date")) if new_data.get("event_date") else None
        if old_event_date != new_event_date:
            alrt = await self._create_alert(cid, "EVENT_DATE_CHANGED", "ACTION_REQUIRED", f"Event Date Changed: {company}", f"Event date changed from {old_event_date} to {new_event_date}.", old_val=old_event_date, new_val=new_event_date)
            if alrt: alerts_generated.append(alrt)
            
        # 4. Registration Deadline Changed
        old_reg = str(old_lead.registration_deadline) if old_lead.registration_deadline else None
        new_reg = str(new_data.get("registration_deadline")) if new_data.get("registration_deadline") else None
        if old_reg != new_reg:
            alrt = await self._create_alert(cid, "REGISTRATION_DEADLINE_CHANGED", "ACTION_REQUIRED", f"Deadline Changed: {company}", f"Registration deadline changed from {old_reg} to {new_reg}.", old_val=old_reg, new_val=new_reg)
            if alrt: alerts_generated.append(alrt)

        # 5. CTC Changed
        old_ctc = old_lead.ctc
        new_ctc = str(new_data.get("ctc")) if new_data.get("ctc") is not None else None
        try:
            f_old = float(old_ctc) if old_ctc else None
            f_new = float(new_ctc) if new_ctc else None
            if f_old != f_new:
                alrt = await self._create_alert(cid, "CTC_CHANGED", "ACTION_REQUIRED", f"CTC Changed: {company}", f"CTC changed from {old_ctc} to {new_ctc}.", old_val=old_ctc, new_val=new_ctc, evidence=new_data.get("source_lineage"))
                if alrt: alerts_generated.append(alrt)
        except ValueError:
            if old_ctc != new_ctc:
                alrt = await self._create_alert(cid, "CTC_CHANGED", "ACTION_REQUIRED", f"CTC Changed: {company}", f"CTC changed from {old_ctc} to {new_ctc}.", old_val=old_ctc, new_val=new_ctc, evidence=new_data.get("source_lineage"))
                if alrt: alerts_generated.append(alrt)

        # 6. Eligibility / Fit Changed
        old_fit = old_lead.target_fit
        new_fit = new_data.get("target_fit")
        if old_fit != new_fit:
            alrt = await self._create_alert(cid, "ELIGIBILITY_CHANGED", "ACTION_REQUIRED", f"Eligibility Changed: {company}", f"Target fit changed from {old_fit} to {new_fit}.", old_val=old_fit, new_val=new_fit)
            if alrt: alerts_generated.append(alrt)

        # 7. Role Changed
        old_role = old_lead.role
        new_role = new_data.get("role")
        if old_role != new_role:
            alrt = await self._create_alert(cid, "ROLE_CHANGED", "INFORMATIONAL", f"Role Changed: {company}", f"Role changed from {old_role} to {new_role}.", old_val=old_role, new_val=new_role)
            if alrt: alerts_generated.append(alrt)
            
        # 8. Branch Fit Changed
        old_branches = json.loads(old_lead.branches) if old_lead.branches else []
        new_branches = new_data.get("branches", [])
        if set(old_branches) != set(new_branches):
            alrt = await self._create_alert(cid, "BRANCH_FIT_CHANGED", "INFORMATIONAL", f"Branches Changed: {company}", f"Branches changed from {old_branches} to {new_branches}.", old_val=old_branches, new_val=new_branches)
            if alrt: alerts_generated.append(alrt)

        # 9. Contact / Phone Changes
        old_contact_status = old_lead.contact_status
        new_contact_status = new_data.get("contact_status")
        
        old_verified_ids = json.loads(old_lead.verified_contact_ids) if old_lead.verified_contact_ids else []
        new_verified_ids = new_data.get("verified_contact_ids", [])
        
        if set(old_verified_ids) != set(new_verified_ids):
            if len(new_verified_ids) > len(old_verified_ids):
                alrt = await self._create_alert(cid, "CONTACT_ADDED", "INFORMATIONAL", f"Contact Added: {company}", f"New contacts added.", old_val=old_verified_ids, new_val=new_verified_ids)
                if alrt: alerts_generated.append(alrt)
            else:
                alrt = await self._create_alert(cid, "CONTACT_CHANGED", "INFORMATIONAL", f"Contact Changed: {company}", f"Contacts updated.", old_val=old_verified_ids, new_val=new_verified_ids)
                if alrt: alerts_generated.append(alrt)
                
            if old_contact_status != "VERIFIED" and new_contact_status == "VERIFIED":
                alrt = await self._create_alert(cid, "PHONE_VERIFIED", "ACTION_REQUIRED", f"Phone Verified: {company}", f"A phone was newly verified.", old_val=old_contact_status, new_val=new_contact_status)
                if alrt: alerts_generated.append(alrt)
            elif old_contact_status == "VERIFIED" and new_contact_status == "VERIFIED" and set(old_verified_ids) != set(new_verified_ids):
                alrt = await self._create_alert(cid, "PHONE_CHANGED", "INFORMATIONAL", f"Phone Changed: {company}", f"Verified phone identity changed.", old_val=old_verified_ids, new_val=new_verified_ids)
                if alrt: alerts_generated.append(alrt)

        if old_contact_status != new_contact_status and new_contact_status == "STALE_SUSPECTED":
            alrt = await self._create_alert(cid, "PHONE_BECAME_STALE", "SYSTEM_WARNING", f"Stale Phone: {company}", f"Phone suspected to be stale.", old_val=old_contact_status, new_val=new_contact_status)
            if alrt: alerts_generated.append(alrt)
            
        # 10. Evidence Changed
        old_lineage = json.loads(old_lead.source_lineage) if old_lead.source_lineage else {}
        new_lineage = new_data.get("source_lineage", {})
        if old_lineage != new_lineage:
            alrt = await self._create_alert(cid, "EVIDENCE_CHANGED", "INFORMATIONAL", f"Evidence Changed: {company}", f"Evidence/lineage was updated.", old_val=old_lineage, new_val=new_lineage)
            if alrt: alerts_generated.append(alrt)
            
        # 11. Source Updated
        old_source_name = old_lead.company_name
        new_source_name = new_data.get("company_name")
        if old_source_name != new_source_name:
            alrt = await self._create_alert(cid, "SOURCE_UPDATED", "INFORMATIONAL", f"Source Updated: {company}", f"Source name updated.", old_val=old_source_name, new_val=new_source_name)
            if alrt: alerts_generated.append(alrt)

        return alerts_generated

    async def detect_new_lead(self, new_data: dict):
        cid = new_data["canonical_event_id"]
        company = new_data.get("company_name", "Unknown")
        alrt = await self._create_alert(cid, "NEW_LEAD", "INFORMATIONAL", f"New Lead: {company}", f"Detected new lead: {company}", old_val=None, new_val=new_data)
        return [alrt] if alrt else []

    async def detect_removed_lead(self, old_lead: OutreachLead):
        cid = old_lead.canonical_event_id
        company = old_lead.company_name or "Unknown"
        alrt = await self._create_alert(cid, "LEAD_REMOVED_FROM_CURRENT_SNAPSHOT", "INFORMATIONAL", f"Lead Removed: {company}", f"Lead removed from snapshot: {company}", old_val=cid, new_val=None)
        return [alrt] if alrt else []
        
    async def detect_restored_lead(self, new_data: dict):
        cid = new_data["canonical_event_id"]
        company = new_data.get("company_name", "Unknown")
        alrt = await self._create_alert(cid, "LEAD_RESTORED", "INFORMATIONAL", f"Lead Restored: {company}", f"Lead restored in snapshot: {company}", old_val=None, new_val=cid)
        return [alrt] if alrt else []
        
    async def log_snapshot_ingested(self, count: int, snapshot_id: str):
        alrt = await self._create_alert(None, "SNAPSHOT_INGESTED", "INFORMATIONAL", f"Snapshot Ingested", f"Ingested {count} records in {snapshot_id}.", old_val=None, new_val=count)
        return [alrt] if alrt else []
        
    async def log_snapshot_failed(self, error: str, snapshot_id: str):
        alrt = await self._create_alert(None, "SNAPSHOT_FAILED", "SYSTEM_WARNING", f"Snapshot Failed", f"Failed to ingest {snapshot_id}: {error}.", old_val=None, new_val=error)
        return [alrt] if alrt else []
        
    async def log_source_health_degraded(self, snapshot_id: str):
        alrt = await self._create_alert(None, "SOURCE_HEALTH_DEGRADED", "SYSTEM_WARNING", f"Source Health Degraded", f"Source health degraded for {snapshot_id}.", old_val=None, new_val=None)
        return [alrt] if alrt else []
