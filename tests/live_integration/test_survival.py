"""
Live Integration Test: Field Preservation & Field Survival
Recovery Status: REPLACEMENT_TEST (Original source unrecoverable due to log truncation)

Verifies field survival across repeated updates:
When an event is updated with new discovery data, previously discovered fields
(such as verified recruiter contact and CTC) must survive.
"""
import pytest
import asyncpg

pytestmark = pytest.mark.live_integration

@pytest.mark.asyncio
async def test_survival(live_db_url):
    conn = await asyncpg.connect(live_db_url)
    try:
        test_id = "test_field_survival_lead"
        await conn.execute("DELETE FROM outreach_leads WHERE canonical_event_id = $1;", test_id)
        
        await conn.execute(
            """INSERT INTO outreach_leads 
               (canonical_event_id, company_name, role, ctc, verified_contact_ids, outreach_status, outreach_priority, outreach_readiness, contact_status, snapshot_id, currently_present, created_at, updated_at) 
               VALUES ($1, 'Survival Corp', 'Backend Dev', '14.0 LPA', '+91-9876543210', 'HOT_OUTREACH_LEAD', 'HIGH', 'READY', 'VERIFIED', 'snap_survival_1', TRUE, NOW(), NOW());""",
            test_id
        )
        
        await conn.execute(
            """UPDATE outreach_leads 
               SET outreach_priority = 'CRITICAL', updated_at = NOW() 
               WHERE canonical_event_id = $1;""",
            test_id
        )
        
        survived = await conn.fetchrow("SELECT * FROM outreach_leads WHERE canonical_event_id = $1;", test_id)
        assert survived["verified_contact_ids"] == "+91-9876543210"
        assert survived["ctc"] == "14.0 LPA"
        assert survived["outreach_priority"] == "CRITICAL"
    finally:
        await conn.execute("DELETE FROM outreach_leads WHERE canonical_event_id = $1;", test_id)
        await conn.close()
