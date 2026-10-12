"""
Live Integration Test: Outreach Lead Immutability
Recovery Status: PARTIALLY_RECOVERED (Core assertions from Task-330 trace)

Verifies that historically recorded source truth on outreach_leads is immutable:
Prohibited mutations to historical lead records must not overwrite established ground truth.
"""
import pytest
import asyncpg

pytestmark = pytest.mark.live_integration

@pytest.mark.asyncio
async def test_immutability(live_db_url):
    conn = await asyncpg.connect(live_db_url)
    try:
        test_id = "test_immutability_canonical_lead"
        await conn.execute("DELETE FROM outreach_leads WHERE canonical_event_id = $1;", test_id)
        
        # 1. Insert original source truth record with established human operational state
        await conn.execute(
            """INSERT INTO outreach_leads 
               (canonical_event_id, company_name, role, ctc, outreach_status, assigned_to, outreach_priority, outreach_readiness, contact_status, snapshot_id, currently_present, created_at, updated_at) 
               VALUES ($1, 'Original Company Ground Truth', 'Software Engineer', '12.0 LPA', 'CONTACTED', 'agent_alice', 'HIGH', 'READY', 'VERIFIED', 'snap_immutability', TRUE, NOW(), NOW());""",
            test_id
        )
        
        source_truth = await conn.fetchrow("SELECT * FROM outreach_leads WHERE canonical_event_id = $1;", test_id)
        assert source_truth is not None
        assert source_truth["company_name"] == "Original Company Ground Truth"
        assert source_truth["ctc"] == "12.0 LPA"
        assert source_truth["outreach_status"] == "CONTACTED"
        assert source_truth["assigned_to"] == "agent_alice"

        # 2. Attempt prohibited mutation 1: Attempt to overwrite identity by inserting duplicate canonical key
        prohibited_mutation_rejected = False
        try:
            await conn.execute(
                """INSERT INTO outreach_leads 
                   (canonical_event_id, company_name, role, ctc, outreach_status, outreach_priority, outreach_readiness, contact_status, snapshot_id, currently_present, created_at, updated_at) 
                   VALUES ($1, 'Hostile Overwrite Corp', 'Mutated Role', '1.0 LPA', 'NEW', 'LOW', 'NOT_READY', 'UNVERIFIED', 'snap_malicious', TRUE, NOW(), NOW());""",
                test_id
            )
        except asyncpg.exceptions.UniqueViolationError:
            prohibited_mutation_rejected = True
        assert prohibited_mutation_rejected, "Prohibited mutation succeeded; database failed to reject duplicate canonical key"

        # 3. Verify that ground truth and operational workflow status remain unchanged
        current_record = await conn.fetchrow("SELECT * FROM outreach_leads WHERE canonical_event_id = $1;", test_id)
        assert current_record["company_name"] == "Original Company Ground Truth"
        assert current_record["ctc"] == "12.0 LPA"
        assert current_record["outreach_status"] == "CONTACTED"
        assert current_record["assigned_to"] == "agent_alice"
        assert current_record["canonical_event_id"] == test_id
    finally:
        await conn.execute("DELETE FROM outreach_leads WHERE canonical_event_id = $1;", test_id)
        await conn.close()
