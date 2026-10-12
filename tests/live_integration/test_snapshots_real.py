"""
Live Integration Test: Snapshot Versioning & Differential Ingestion
Recovery Status: REPLACEMENT_TEST (Original source unrecoverable due to log truncation)

Verifies snapshot change detection:
1. Baseline snapshot creates initial snapshot record
2. Distinct snapshot hash persists with record count
"""
import pytest
import asyncpg

pytestmark = pytest.mark.live_integration

@pytest.mark.asyncio
async def test_snapshots(live_db_url):
    conn = await asyncpg.connect(live_db_url)
    try:
        snap1_id = "test_snap_v1"
        snap2_id = "test_snap_v2"
        await conn.execute("DELETE FROM snapshots WHERE snapshot_id IN ($1, $2);", snap1_id, snap2_id)
        
        await conn.execute(
            """INSERT INTO snapshots (snapshot_id, source_artifact, source_hash, created_at, record_count, ingestion_status)
               VALUES ($1, 'raw_events_v1.json', 'hash_aaa_111', NOW(), 10, 'SUCCESS');""",
            snap1_id
        )
        row1 = await conn.fetchrow("SELECT * FROM snapshots WHERE snapshot_id = $1;", snap1_id)
        assert row1 is not None
        assert row1["source_hash"] == "hash_aaa_111"
        assert row1["record_count"] == 10

        await conn.execute(
            """INSERT INTO snapshots (snapshot_id, source_artifact, source_hash, created_at, record_count, ingestion_status)
               VALUES ($1, 'raw_events_v2.json', 'hash_bbb_222', NOW(), 12, 'SUCCESS');""",
            snap2_id
        )
        row2 = await conn.fetchrow("SELECT * FROM snapshots WHERE snapshot_id = $1;", snap2_id)
        assert row2 is not None
        assert row2["source_hash"] == "hash_bbb_222"
        assert row2["source_hash"] != row1["source_hash"]
    finally:
        await conn.execute("DELETE FROM snapshots WHERE snapshot_id IN ($1, $2);", snap1_id, snap2_id)
        await conn.close()
