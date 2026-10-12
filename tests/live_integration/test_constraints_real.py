"""
Live Integration Test: Database Constraints
Recovery Status: EXACT_RECOVERED (Task-330 trace) + Substantive Enhancements

Verifies that PostgreSQL schema constraints are strictly enforced:
1. Unique primary key (canonical_event_id) on outreach_leads
2. Unique source_hash constraint on snapshots
3. Indices on outreach_priority, company_name, outreach_status
4. Check constraints and table structure integrity
"""
import pytest
import asyncpg

pytestmark = pytest.mark.live_integration

@pytest.mark.asyncio
async def test_constraints(live_db_url):
    conn = await asyncpg.connect(live_db_url)
    try:
        # 1. Unique canonical event ID index / primary key on outreach_leads
        lead_indexes = await conn.fetch(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'outreach_leads' AND indexdef LIKE '%UNIQUE%';"
        )
        assert len(lead_indexes) > 0, "outreach_leads lacks required UNIQUE index / primary key"
        has_pk = any("canonical_event_id" in row["indexdef"] or "outreach_leads_pkey" in row["indexname"] for row in lead_indexes)
        assert has_pk, "outreach_leads missing UNIQUE constraint on canonical_event_id"

        # 2. Unique source hash constraint on snapshots
        snap_indexes = await conn.fetch(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'snapshots' AND indexdef LIKE '%UNIQUE%';"
        )
        assert len(snap_indexes) > 0, "snapshots table lacks required UNIQUE index"
        has_hash_uq = any("source_hash" in row["indexdef"] or "snapshots_source_hash_key" in row["indexname"] for row in snap_indexes)
        assert has_hash_uq, "snapshots table missing UNIQUE constraint on source_hash"

        # 3. Individual required query performance indices
        all_indexes = [row["indexname"] for row in await conn.fetch(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'outreach_leads';"
        )]
        for req_idx in ["ix_outreach_leads_outreach_priority", "ix_outreach_leads_company_name", "ix_outreach_leads_outreach_status"]:
            assert req_idx in all_indexes, f"Missing required performance index: {req_idx}"

        # 4. Enforce duplicate key rejection at the DB layer
        test_id = "test_constraint_dup_event"
        await conn.execute("DELETE FROM outreach_leads WHERE canonical_event_id = $1;", test_id)
        await conn.execute(
            """INSERT INTO outreach_leads 
               (canonical_event_id, company_name, outreach_status, outreach_priority, outreach_readiness, contact_status, snapshot_id, currently_present, created_at, updated_at) 
               VALUES ($1, 'Constraint Test Corp', 'HOT_OUTREACH_LEAD', 'HIGH', 'READY', 'VERIFIED', 'snap_test_1', TRUE, NOW(), NOW());""",
            test_id
        )
        duplicate_raised = False
        try:
            await conn.execute(
                """INSERT INTO outreach_leads 
                   (canonical_event_id, company_name, outreach_status, outreach_priority, outreach_readiness, contact_status, snapshot_id, currently_present, created_at, updated_at) 
                   VALUES ($1, 'Constraint Duplicate', 'ACTIVE_OPPORTUNITY', 'MEDIUM', 'READY', 'VERIFIED', 'snap_test_1', TRUE, NOW(), NOW());""",
                test_id
            )
        except asyncpg.exceptions.UniqueViolationError:
            duplicate_raised = True
        finally:
            await conn.execute("DELETE FROM outreach_leads WHERE canonical_event_id = $1;", test_id)
            
        assert duplicate_raised, "Database failed to enforce UniqueViolationError on duplicate canonical_event_id"
    finally:
        await conn.close()
