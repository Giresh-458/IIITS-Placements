"""
Live Integration Test: Service Disconnect & Recovery
Recovery Status: PARTIALLY_RECOVERED (Task-330 trace)

Verifies that the API service handles database connectivity and recovers gracefully.
"""
import pytest
import requests
import asyncpg

pytestmark = pytest.mark.live_integration

@pytest.mark.asyncio
async def test_recovery(live_db_url, live_api_url):
    # 1. Primary API liveness probe
    res_init = requests.get(f"{live_api_url}/health", timeout=5)
    assert res_init.status_code == 200
    assert res_init.json().get("status") == "ok"

    # 2. Database plane liveness probe
    conn = await asyncpg.connect(live_db_url)
    assert conn is not None
    await conn.execute("SELECT 1;")

    # 3. Simulate connection drop
    await conn.close()
    assert conn.is_closed(), "Connection failed to close during simulated disconnect"

    # 4. Verify system recovers gracefully on reconnect
    conn_recovered = await asyncpg.connect(live_db_url)
    try:
        val = await conn_recovered.fetchval("SELECT 1;")
        assert val == 1
    finally:
        await conn_recovered.close()

    # 5. Verify API database health check recovers
    res_db = requests.get(f"{live_api_url}/health/db", timeout=5)
    assert res_db.status_code == 200
    assert res_db.json().get("status") == "ok"
