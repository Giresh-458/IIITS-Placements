"""
Live Integration Test: Ingestion Transactional Rollback
Recovery Status: REPLACEMENT_TEST (Original source unrecoverable due to log truncation)

Verifies all-or-nothing transactional integrity:
If an error occurs mid-ingestion, the entire batch transaction must roll back cleanly.
No partial writes may persist in the database.
"""
import pytest
import asyncpg

import json
import os
import tempfile
from src.storage.database import DatabaseManager
from src.orchestration.ingestion import Batch9Ingestion, IngestionError

pytestmark = pytest.mark.live_integration

@pytest.mark.asyncio
async def test_rollback(live_db_url):
    conn = await asyncpg.connect(live_db_url)
    try:
        tag = "test_rollback_batch_"
        await conn.execute("DELETE FROM outreach_leads WHERE canonical_event_id LIKE $1;", f"{tag}%")
        
        count_before = await conn.fetchval(
            "SELECT count(*) FROM outreach_leads WHERE canonical_event_id LIKE $1;", f"{tag}%"
        )
        assert count_before == 0

        # 1. Test application-level Ingestion transactional rollback
        db_mgr = DatabaseManager(live_db_url.replace("postgresql://", "postgresql+asyncpg://"))
        await db_mgr.connect()
        try:
            ingestion = Batch9Ingestion(db_mgr)
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f_leads, \
                 tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f_contacts:
                # Corrupt payload with duplicate canonical_event_id violating application invariant
                json.dump([
                    {"canonical_event_id": f"{tag}app1", "company_name": "App Co 1", "source_lineage": {}},
                    {"canonical_event_id": f"{tag}app1", "company_name": "App Co 1 Duplicate", "source_lineage": {}}
                ], f_leads)
                json.dump([], f_contacts)
                leads_file = f_leads.name
                contacts_file = f_contacts.name

            try:
                with pytest.raises(IngestionError, match="Duplicate canonical IDs"):
                    await ingestion.ingest_snapshot(leads_file, contacts_file)
            finally:
                if os.path.exists(leads_file): os.unlink(leads_file)
                if os.path.exists(contacts_file): os.unlink(contacts_file)

            # Assert application transaction aborted: 0 partial leads persisted
            count_app = await conn.fetchval(
                "SELECT count(*) FROM outreach_leads WHERE canonical_event_id LIKE $1;", f"{tag}%"
            )
            assert count_app == 0, f"Application rollback failed: {count_app} partial rows persisted"
        finally:
            await db_mgr.disconnect()

        # 2. Test database-level transactional rollback with mid-stream abort
        rollback_caught = False
        try:
            async with conn.transaction():
                await conn.execute(
                    """INSERT INTO outreach_leads 
                       (canonical_event_id, company_name, outreach_status, outreach_priority, outreach_readiness, contact_status, snapshot_id, currently_present, created_at, updated_at) 
                       VALUES ($1, 'Rollback Corp 1', 'ACTIVE_OPPORTUNITY', 'MEDIUM', 'READY', 'VERIFIED', 'snap_rollback_1', TRUE, NOW(), NOW());""",
                    f"{tag}1"
                )
                raise RuntimeError("Simulated mid-batch database failure before commit")
        except RuntimeError as e:
            rollback_caught = True
            assert "Simulated mid-batch database failure" in str(e)

        assert rollback_caught, "Simulated failure was not caught"

        count_after = await conn.fetchval(
            "SELECT count(*) FROM outreach_leads WHERE canonical_event_id LIKE $1;", f"{tag}%"
        )
        assert count_after == 0, f"Transactional rollback failed: {count_after} partial rows persisted"
    finally:
        await conn.execute("DELETE FROM outreach_leads WHERE canonical_event_id LIKE $1;", f"{tag}%")
        await conn.close()
