"""
Live Integration Test: API Core Endpoints Contract
Recovery Status: PARTIALLY_RECOVERED (Task-330 trace) + Contract Assertions

Verifies that the live FastAPI application fulfills its endpoint contracts:
1. /health returns status 200 with database health status
2. /leads/stats/summary returns valid non-negative metrics
"""
import pytest
import requests

pytestmark = pytest.mark.live_integration

def test_api(live_api_url):
    res_health = requests.get(f"{live_api_url}/health", timeout=5)
    assert res_health.status_code == 200, f"Health endpoint failed: {res_health.status_code}"
    health_data = res_health.json()
    assert health_data.get("status") == "ok"

    res_db = requests.get(f"{live_api_url}/health/db", timeout=5)
    assert res_db.status_code == 200, f"DB Health endpoint failed: {res_db.status_code}"
    assert res_db.json().get("status") == "ok"

    res_stats = requests.get(f"{live_api_url}/leads/stats/summary", timeout=5)
    assert res_stats.status_code == 200, f"Stats endpoint failed: {res_stats.status_code}"
    stats_data = res_stats.json()
    assert "total_leads" in stats_data
    assert isinstance(stats_data["total_leads"], int)
    assert stats_data["total_leads"] >= 0
    for dict_field in ["by_priority", "by_contact_status", "by_operational_status"]:
        assert dict_field in stats_data
        assert isinstance(stats_data[dict_field], dict)
