import json
import hashlib
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from src.storage.models.outreach import OutreachLead, OutreachContact, SnapshotMetadata, AuditLog
from src.orchestration.change_detector import ChangeDetector

class IngestionError(Exception):
    pass

class Batch9Ingestion:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def hash_artifact(self, filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    async def ingest_snapshot(self, leads_path: str, contacts_path: str) -> dict:
        """
        Idempotent ingestion of Batch 8 artifacts.
        """
        try:
            leads_hash = self.hash_artifact(leads_path)
            
            with open(leads_path, 'r', encoding='utf-8') as f:
                leads_data = json.load(f)
                
            with open(contacts_path, 'r', encoding='utf-8') as f:
                contacts_data = json.load(f)
        except Exception as e:
            raise IngestionError(f"Failed to load artifacts: {e}")

        # Basic schema validation
        if not isinstance(leads_data, list):
            raise IngestionError("Invalid schema: leads data must be a list")
            
        for l in leads_data:
            if "canonical_event_id" not in l or "source_lineage" not in l:
                raise IngestionError("Missing required provenance in lead")
                
        snapshot_id = f"snap_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{leads_hash[:8]}"

        async with self.db_manager.session_maker() as session:
            try:
                # Check for idempotent hash
                result = await session.execute(select(SnapshotMetadata).where(SnapshotMetadata.source_hash == leads_hash))
                existing_snap = result.scalar_one_or_none()
                if existing_snap:
                    logging.info(f"Snapshot already ingested: {leads_hash}")
                    # Log lifecycle alert even on bypass
                    detector = ChangeDetector(session, existing_snap.snapshot_id)
                    alerts = await detector.log_snapshot_ingested(len(leads_data), existing_snap.snapshot_id)
                    await session.commit()
                    return {
                        "status": "SUCCESS",
                        "snapshot_id": existing_snap.snapshot_id,
                        "inserted": 0,
                        "updated": 0,
                        "unchanged": len(leads_data),
                        "rejected": 0,
                        "alerts_generated": len(alerts)
                    }

                # Mark previously currently_present leads to False ONLY if they are missing.
                # Handled below in Batch 10 logic.
                
                snap = SnapshotMetadata(
                    snapshot_id=snapshot_id,
                    source_artifact=leads_path,
                    source_hash=leads_hash,
                    record_count=len(leads_data),
                    ingestion_status="SUCCESS"
                )
                session.add(snap)

                inserted_leads = 0
                updated_leads = 0
                alerts_generated = []
                detector = ChangeDetector(session, snapshot_id)
                
                # Check for removed leads (in DB as currently_present=True, but missing in new snapshot)
                lead_ids = [l["canonical_event_id"] for l in leads_data]
                if len(lead_ids) != len(set(lead_ids)):
                    raise IngestionError("Duplicate canonical IDs in input")
                    
                present_res = await session.execute(select(OutreachLead).where(OutreachLead.currently_present == True))
                present_leads = present_res.scalars().all()
                for pl in present_leads:
                    if pl.canonical_event_id not in lead_ids:
                        pl.currently_present = False
                        alrts = await detector.detect_removed_lead(pl)
                        alerts_generated.extend(alrts)
                
                # Fetch existing leads to compare
                result = await session.execute(select(OutreachLead).where(OutreachLead.canonical_event_id.in_(lead_ids)))
                existing_leads = {l.canonical_event_id: l for l in result.scalars().all()}

                for lead_dict in leads_data:
                    cid = lead_dict["canonical_event_id"]
                    if cid in existing_leads:
                        existing_lead = existing_leads[cid]
                        
                        # Generate restored lead alert if it was absent previously
                        if not existing_lead.currently_present:
                            alrts = await detector.detect_restored_lead(lead_dict)
                            alerts_generated.extend(alrts)
                        
                        # Detect changes BEFORE modifying existing_lead
                        alrts = await detector.detect_changes_for_lead(lead_dict, existing_lead)
                        alerts_generated.extend(alrts)
                        
                        # Only update source fields
                        existing_lead.company_name = lead_dict.get("company_name")
                        existing_lead.role = lead_dict.get("role")
                        existing_lead.batch = lead_dict.get("batch")
                        existing_lead.branches = json.dumps(lead_dict.get("branches", []))
                        existing_lead.ctc = lead_dict.get("ctc")
                        if existing_lead.ctc is not None:
                            existing_lead.ctc = str(existing_lead.ctc)
                        existing_lead.event_date = lead_dict.get("event_date")
                        existing_lead.registration_deadline = lead_dict.get("registration_deadline")
                        existing_lead.role_relevance = lead_dict.get("role_relevance")
                        existing_lead.fresher_scope = lead_dict.get("fresher_scope")
                        existing_lead.branch_qualification = lead_dict.get("branch_qualification")
                        existing_lead.package_qualification = lead_dict.get("package_qualification")
                        existing_lead.target_fit = lead_dict.get("target_fit")
                        existing_lead.temporal_status = lead_dict.get("temporal_status")
                        existing_lead.outreach_priority = lead_dict.get("outreach_priority")
                        existing_lead.outreach_readiness = lead_dict.get("outreach_readiness")
                        existing_lead.contact_status = lead_dict.get("contact_status")
                        existing_lead.verified_contact_ids = json.dumps(lead_dict.get("verified_contact_ids", []))
                        existing_lead.priority_reason = lead_dict.get("priority_reason")
                        existing_lead.readiness_reason = lead_dict.get("readiness_reason")
                        existing_lead.source_lineage = json.dumps(lead_dict.get("source_lineage", {}))
                        existing_lead.snapshot_id = snapshot_id
                        existing_lead.currently_present = True
                        
                        updated_leads += 1
                        
                        audit = AuditLog(
                            entity_type="LEAD",
                            entity_id=cid,
                            action="SNAPSHOT_UPDATED",
                            reason=f"Ingested snapshot {snapshot_id}"
                        )
                        session.add(audit)
                    else:
                        alrts = await detector.detect_new_lead(lead_dict)
                        alerts_generated.extend(alrts)
                        
                        ctc_val = lead_dict.get("ctc")
                        new_lead = OutreachLead(
                            canonical_event_id=cid,
                            company_name=lead_dict.get("company_name"),
                            role=lead_dict.get("role"),
                            batch=lead_dict.get("batch"),
                            branches=json.dumps(lead_dict.get("branches", [])),
                            ctc=str(ctc_val) if ctc_val is not None else None,
                            event_date=lead_dict.get("event_date"),
                            registration_deadline=lead_dict.get("registration_deadline"),
                            role_relevance=lead_dict.get("role_relevance"),
                            fresher_scope=lead_dict.get("fresher_scope"),
                            branch_qualification=lead_dict.get("branch_qualification"),
                            package_qualification=lead_dict.get("package_qualification"),
                            target_fit=lead_dict.get("target_fit"),
                            temporal_status=lead_dict.get("temporal_status"),
                            outreach_priority=lead_dict.get("outreach_priority"),
                            outreach_readiness=lead_dict.get("outreach_readiness"),
                            contact_status=lead_dict.get("contact_status"),
                            verified_contact_ids=json.dumps(lead_dict.get("verified_contact_ids", [])),
                            priority_reason=lead_dict.get("priority_reason"),
                            readiness_reason=lead_dict.get("readiness_reason"),
                            source_lineage=json.dumps(lead_dict.get("source_lineage", {})),
                            snapshot_id=snapshot_id,
                            currently_present=True
                        )
                        session.add(new_lead)
                        inserted_leads += 1
                        
                        audit = AuditLog(
                            entity_type="LEAD",
                            entity_id=cid,
                            action="SNAPSHOT_CREATED",
                            reason=f"Ingested snapshot {snapshot_id}"
                        )
                        session.add(audit)

                # Contacts
                result = await session.execute(select(OutreachContact).where(OutreachContact.contact_id.in_([c["contact_id"] for c in contacts_data])))
                existing_contacts = {c.contact_id: c for c in result.scalars().all()}
                
                for contact_dict in contacts_data:
                    c_id = contact_dict["contact_id"]
                    if c_id in existing_contacts:
                        existing = existing_contacts[c_id]
                        existing.company = contact_dict.get("company")
                        existing.person_name = contact_dict.get("person_name")
                        existing.contact_role = contact_dict.get("contact_role")
                        existing.phone = contact_dict.get("phone")
                        existing.verification_state = contact_dict.get("verification_state")
                        existing.confidence = contact_dict.get("confidence")
                        existing.linked_event_ids = json.dumps(contact_dict.get("linked_event_ids", []))
                        existing.evidence = json.dumps(contact_dict.get("evidence", {}))
                        existing.snapshot_id = snapshot_id
                    else:
                        new_c = OutreachContact(
                            contact_id=c_id,
                            company=contact_dict.get("company"),
                            person_name=contact_dict.get("person_name"),
                            contact_role=contact_dict.get("contact_role"),
                            phone=contact_dict.get("phone"),
                            verification_state=contact_dict.get("verification_state"),
                            confidence=contact_dict.get("confidence"),
                            linked_event_ids=json.dumps(contact_dict.get("linked_event_ids", [])),
                            evidence=json.dumps(contact_dict.get("evidence", {})),
                            snapshot_id=snapshot_id
                        )
                        session.add(new_c)

                # Snapshot Ingested Alert
                alrts = await detector.log_snapshot_ingested(len(leads_data), snapshot_id)
                alerts_generated.extend(alrts)
                
                await session.commit()
                
                # Write diff artifact
                diff_data = {
                    "previous_snapshot": None,
                    "current_snapshot": snapshot_id,
                    "new_leads": len([a for a in alerts_generated if a.alert_type == "NEW_LEAD"]),
                    "removed_leads": len([a for a in alerts_generated if a.alert_type == "LEAD_REMOVED_FROM_CURRENT_SNAPSHOT"]),
                    "restored_leads": len([a for a in alerts_generated if a.alert_type == "LEAD_RESTORED"]),
                    "alerts_generated": [
                        {
                            "id": a.id,
                            "type": a.alert_type,
                            "lead_id": a.lead_id,
                            "priority": a.priority,
                            "old": a.old_value,
                            "new": a.new_value
                        } for a in alerts_generated
                    ]
                }
                
                try:
                    with open("artifacts/batch_10_snapshot_diff.json", "w") as f:
                        json.dump(diff_data, f, indent=2)
                except Exception:
                    pass
                
                return {
                    "status": "SUCCESS",
                    "snapshot_id": snapshot_id,
                    "inserted": inserted_leads,
                    "updated": updated_leads,
                    "unchanged": 0,
                    "rejected": 0,
                    "alerts_generated": len(alerts_generated)
                }
            except Exception as e:
                await session.rollback()
                logging.error(f"Ingestion transaction failed: {e}")
                # Log snapshot failed alert in a new transaction
                async with self.db_manager.session_maker() as fallback_session:
                    try:
                        det = ChangeDetector(fallback_session, snapshot_id)
                        await det.log_snapshot_failed(str(e), snapshot_id)
                        await fallback_session.commit()
                    except Exception as nested_e:
                        logging.error(f"Failed to log snapshot failure: {nested_e}")
                raise IngestionError(str(e))
