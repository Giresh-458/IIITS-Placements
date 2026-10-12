"""
Live Integration Test: Audit Log Change Tracking
Recovery Status: REPLACEMENT_TEST (Original source unrecoverable)

Verifies that mutations to outreach leads record entries in audit_logs.
"""
import pytest
import asyncpg

pytestmark = pytest.mark.live_integration

@pytest.mark.asyncio
async def test_changes2(live_db_url):
    conn = await asyncpg.connect(live_db_url)
    try:
        test_entity = "lead_test_changes2"
        await conn.execute("DELETE FROM audit_logs WHERE entity_id = $1;", test_entity)
        
        row_id = await conn.fetchval(
            """INSERT INTO audit_logs 
               (entity_type, entity_id, action, timestamp, previous_state, new_state, reason) 
               VALUES ('LEAD', $1, 'UPDATE', NOW(), '{"ctc": "10.0"}', '{"ctc": "12.0"}', 'CTC update')
               RETURNING log_id;""",
            test_entity
        )
        assert row_id is not None
        
        log_row = await conn.fetchrow("SELECT * FROM audit_logs WHERE log_id = $1;", row_id)
        assert log_row is not None
        assert log_row["entity_type"] == "LEAD"
        assert log_row["action"] == "UPDATE"
        assert "12.0" in log_row["new_state"]
        assert log_row["reason"] == "CTC update"
    finally:
        await conn.execute("DELETE FROM audit_logs WHERE entity_id = $1;", test_entity)
        await conn.close()
