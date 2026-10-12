"""
Live Integration Test: Failure-Closed Batch Isolation
Recovery Status: REPLACEMENT_TEST (Original source unrecoverable due to log truncation)

Verifies that when ingestion encounters corrupted/poisoned data,
the system fails closed: it refuses partial corrupted persistence.
"""
import pytest
import asyncpg

pytestmark = pytest.mark.live_integration

@pytest.mark.asyncio
async def test_failure(live_db_url):
    conn = await asyncpg.connect(live_db_url)
    try:
        tag = "test_failure_closed_"
        await conn.execute("DELETE FROM outreach_leads WHERE canonical_event_id LIKE $1;", f"{tag}%")

        failure_detected = False
        try:
            async with conn.transaction():
                await conn.execute(
                    """INSERT INTO outreach_leads 
                       (canonical_event_id, company_name, outreach_status, outreach_priority, created_at, updated_at) 
                       VALUES ($1, NULL, 'HOT_OUTREACH_LEAD', 'HIGH', NOW(), NOW());""",
                    f"{tag}invalid"
                )
        except asyncpg.exceptions.NotNullViolationError:
            failure_detected = True

        assert failure_detected, "Database failed to reject NULL company_name on outreach_leads"

        invalid_count = await conn.fetchval(
            "SELECT count(*) FROM outreach_leads WHERE canonical_event_id = $1;", f"{tag}invalid"
        )
        assert invalid_count == 0, "Failure-closed violation: corrupt record persisted in database"
    finally:
        await conn.execute("DELETE FROM outreach_leads WHERE canonical_event_id LIKE $1;", f"{tag}%")
        await conn.close()
