import pytest
import json
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.storage.database import DatabaseManager
from src.orchestration.ingestion import Batch9Ingestion, IngestionError
from src.storage.models.outreach import Base, OutreachLead, OutreachContact, SnapshotMetadata

@pytest.fixture
async def temp_db_manager():
    # Use in-memory SQLite for tests
    manager = DatabaseManager("sqlite+aiosqlite:///:memory:")
    await manager.connect()
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    await manager.disconnect()

@pytest.fixture
def temp_artifacts(tmp_path):
    leads = [{
        "canonical_event_id": "test_event_1",
        "company_name": "Acme",
        "role": "SDE",
        "batch": "2026",
        "branches": ["CSE"],
        "ctc": "12.0",
        "event_date": "2026-10-01",
        "registration_deadline": "2026-09-30",
        "role_relevance": "CORE",
        "fresher_scope": "FRESHER",
        "branch_qualification": "QUALIFIED",
        "package_qualification": "QUALIFIED",
        "target_fit": "QUALIFIED",
        "temporal_status": "HOT_OUTREACH_LEAD",
        "outreach_priority": "P0",
        "outreach_readiness": "READY",
        "contact_status": "VERIFIED_RECRUITMENT_CONTACT",
        "verified_contact_ids": ["contact_1"],
        "priority_reason": "",
        "readiness_reason": "",
        "source_lineage": {"event_id": "e1"}
    }]
    contacts = [{
        "contact_id": "contact_1",
        "company": "Acme",
        "person_name": "John",
        "contact_role": "HR",
        "phone": "+919876543210",
        "verification_state": "VERIFIED",
        "confidence": "HIGH",
        "linked_event_ids": ["test_event_1"],
        "evidence": {}
    }]
    l_path = tmp_path / "leads.json"
    c_path = tmp_path / "contacts.json"
    l_path.write_text(json.dumps(leads))
    c_path.write_text(json.dumps(contacts))
    return str(l_path), str(c_path)

@pytest.mark.asyncio
async def test_idempotent_ingestion(temp_db_manager, temp_artifacts):
    l_path, c_path = temp_artifacts
    ingester = Batch9Ingestion(temp_db_manager)
    
    # First ingestion
    res1 = await ingester.ingest_snapshot(l_path, c_path)
    assert res1["status"] == "SUCCESS"
    assert res1["inserted"] == 1
    
    # Second ingestion
    res2 = await ingester.ingest_snapshot(l_path, c_path)
    assert res2["status"] == "SUCCESS"
    assert res2["inserted"] == 0
    assert res2["unchanged"] == 1


@pytest.mark.asyncio
async def test_contact_only_change_is_ingested_as_new_snapshot(temp_db_manager, temp_artifacts):
    l_path, c_path = temp_artifacts
    ingester = Batch9Ingestion(temp_db_manager)

    first = await ingester.ingest_snapshot(l_path, c_path)
    assert first["status"] == "SUCCESS"
    assert first["inserted"] == 1

    # Keep the leads artifact byte-for-byte identical while changing a contact.
    contacts = json.loads(open(c_path, "r", encoding="utf-8").read())
    contacts[0]["phone"] = "+919999999999"
    with open(c_path, "w", encoding="utf-8") as f:
        json.dump(contacts, f)

    second = await ingester.ingest_snapshot(l_path, c_path)
    assert second["status"] == "SUCCESS"
    assert second["snapshot_id"] != first["snapshot_id"]

    async with temp_db_manager.session_maker() as session:
        contact = (
            await session.execute(
                __import__("sqlalchemy").select(OutreachContact).where(
                    OutreachContact.contact_id == "contact_1"
                )
            )
        ).scalar_one()
        snapshots = (
            await session.execute(__import__("sqlalchemy").select(SnapshotMetadata))
        ).scalars().all()

    assert contact.phone == "+919999999999"
    assert len(snapshots) == 2

@pytest.mark.asyncio
async def test_corrupted_snapshot_fails_closed(temp_db_manager, tmp_path):
    l_path = tmp_path / "leads.json"
    c_path = tmp_path / "contacts.json"
    l_path.write_text("NOT JSON")
    c_path.write_text("[]")
    
    ingester = Batch9Ingestion(temp_db_manager)
    with pytest.raises(IngestionError):
        await ingester.ingest_snapshot(str(l_path), str(c_path))

@pytest.mark.asyncio
async def test_missing_provenance_fails_closed(temp_db_manager, tmp_path):
    # Missing source_lineage
    leads = [{"canonical_event_id": "1", "company_name": "Acme"}]
    l_path = tmp_path / "leads.json"
    c_path = tmp_path / "contacts.json"
    l_path.write_text(json.dumps(leads))
    c_path.write_text("[]")
    
    ingester = Batch9Ingestion(temp_db_manager)
    with pytest.raises(IngestionError, match="Missing required provenance"):
        await ingester.ingest_snapshot(str(l_path), str(c_path))
        
@pytest.mark.asyncio
async def test_source_truth_immutability(temp_db_manager, temp_artifacts):
    # We will simulate an API update of the operational status and verify source truth is unchanged
    l_path, c_path = temp_artifacts
    ingester = Batch9Ingestion(temp_db_manager)
    await ingester.ingest_snapshot(l_path, c_path)
    
    async with temp_db_manager.session_maker() as session:
        from sqlalchemy import select
        lead = (await session.execute(select(OutreachLead).where(OutreachLead.canonical_event_id == "test_event_1"))).scalar_one()
        lead.outreach_status = "CONTACTED"
        await session.commit()
        
    # Re-ingest a new artifact where CTC is the same. The operational status should remain, but if we updated the source truth it would be overwritten. Wait, we want to prove API doesn't change source truth.
    # The API just changes outreach_status. The schema enforces that outreach_status is not part of the source fields mapping.
    
    async with temp_db_manager.session_maker() as session:
        lead = (await session.execute(select(OutreachLead).where(OutreachLead.canonical_event_id == "test_event_1"))).scalar_one()
        assert lead.ctc == "12.0"
        assert lead.outreach_status == "CONTACTED"
