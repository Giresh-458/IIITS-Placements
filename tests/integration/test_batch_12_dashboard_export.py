import pytest
from fastapi.testclient import TestClient
from src.app.main import app, db_manager
from src.storage.database import Base
from src.storage.models.outreach import OutreachLead
from sqlalchemy import text
import csv
import io

client = TestClient(app)

@pytest.fixture(autouse=True)
async def setup_db():
    await db_manager.connect()
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        
    async with db_manager.session_maker() as session:
        # 1. OutreachLeads
        leads = [
            OutreachLead(canonical_event_id="1", company_name="Active1", temporal_status="ACTIVE_OPPORTUNITY", outreach_priority="P1", outreach_readiness="READY", contact_status="UNKNOWN", snapshot_id="s1", currently_present=True),
            OutreachLead(canonical_event_id="2", company_name="Active2", temporal_status="ACTIVE_OPPORTUNITY", outreach_priority="P1", outreach_readiness="READY", contact_status="UNKNOWN", snapshot_id="s1", currently_present=True),
            OutreachLead(canonical_event_id="3", company_name="Hot1", temporal_status="HOT_OUTREACH_LEAD", outreach_priority="P1", outreach_readiness="READY", contact_status="UNKNOWN", snapshot_id="s1", currently_present=True),
            OutreachLead(canonical_event_id="4", company_name="Stale1", temporal_status="STALE", outreach_priority="P1", outreach_readiness="READY", contact_status="UNKNOWN", snapshot_id="s1", currently_present=True),
            OutreachLead(canonical_event_id="5", company_name="Unknown1", temporal_status="UNKNOWN", outreach_priority="P1", outreach_readiness="READY", contact_status="UNKNOWN", snapshot_id="s1", currently_present=True),
            OutreachLead(canonical_event_id="6", company_name="Filtered", target_fit="FILTERED_OUT", temporal_status="STALE", outreach_priority="P1", outreach_readiness="READY", contact_status="UNKNOWN", snapshot_id="s1", currently_present=True)
        ]
        session.add_all(leads)
        
        # 2. OutreachContacts (Company contact, College contact, Phone verification cases)
        from src.storage.models.outreach import OutreachContact
        contacts = [
            OutreachContact(contact_id="c1", company="Active1", person_name="HR Alice", contact_role="HR", phone="1234567890", verification_state="VERIFIED", confidence="HIGH", snapshot_id="s1"),
            OutreachContact(contact_id="c2", company="College", person_name="TPO Bob", contact_role="TPO", phone="0987654321", verification_state="UNVERIFIED", confidence="LOW", snapshot_id="s1"),
            OutreachContact(contact_id="c3", company="Active2", person_name="Generic", contact_role="UNKNOWN", phone=None, verification_state="NO_VERIFIED_PUBLIC_RECRUITMENT_PHONE", confidence="NONE", snapshot_id="s1")
        ]
        session.add_all(contacts)
        await session.commit()
        
    # 3. Run History mock (writing to artifacts/run_history.jsonl)
    import os
    os.makedirs("artifacts", exist_ok=True)
    with open("artifacts/run_history.jsonl", "w", encoding="utf-8") as f:
        f.write('{"run_id": "RUN_A", "started_at": "2026-10-08T10:00", "completed_at": "2026-10-08T10:05", "terminal_status": "SUCCESS", "telemetry": {"total_duration_seconds": 300, "qualified_events": 10}}\n')
        f.write('{"run_id": "RUN_B", "started_at": "2026-10-08T11:00", "completed_at": "2026-10-08T11:01", "terminal_status": "SUCCESS", "telemetry": {"total_duration_seconds": 60, "qualified_events": 5}}\n')

@pytest.mark.asyncio
async def test_api_active_vs_hot():
    with TestClient(app) as client:
        print("\n--- EXPORT VERIFICATION ---")
        
        exports = ["active_opportunities", "hot_outreach_leads", "companies", "contacts", "phones", "run_history"]
        for exp in exports:
            resp = client.get(f"/leads/export/{exp}")
            assert resp.status_code == 200
            content_type = resp.headers.get("content-type", "")
            assert "text/csv" in content_type
            
            reader = csv.reader(io.StringIO(resp.text))
            rows = list(reader)
            row_count = len(rows) - 1 if rows else 0
            
            valid = "PASS"
            
            if exp == "active_opportunities":
                assert row_count == 2
                ids = [r[0] for r in rows[1:]]
                assert set(ids) == {"1", "2"}
                assert not {"3", "4", "5", "6"} & set(ids)
            elif exp == "hot_outreach_leads":
                assert row_count == 1
                ids = [r[0] for r in rows[1:]]
                assert set(ids) == {"3"}
                assert not {"1", "6"} & set(ids)
            elif exp == "companies":
                assert row_count == 6
                companies = [r[0] for r in rows[1:]]
                assert "Active1" in companies
                assert "Filtered" in companies
            elif exp == "contacts":
                assert row_count == 3
                names = [r[2] for r in rows[1:]]
                assert "HR Alice" in names
                assert "TPO Bob" in names
                roles = [r[3] for r in rows[1:]]
                assert "HR" in roles
                assert "TPO" in roles
            elif exp == "phones":
                assert row_count == 3
                states = [r[5] for r in rows[1:]]
                assert "VERIFIED" in states
                assert "UNVERIFIED" in states
                assert "NO_VERIFIED_PUBLIC_RECRUITMENT_PHONE" in states
            elif exp == "run_history":
                assert row_count >= 2
                run_ids = [r[0] for r in rows[1:]]
                assert "RUN_A" in run_ids
                assert "RUN_B" in run_ids
                
            print(f"{exp:<25} -> {resp.status_code} / {row_count} rows / content_valid = PASS")
                
        print("--- ALL VERIFICATIONS PASSED ---")
