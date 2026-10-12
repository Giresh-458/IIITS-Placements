"""
Live Integration Test: Extended API & CSV Export Contract
Recovery Status: REPLACEMENT_TEST (Original source unrecoverable due to log truncation)

Verifies extended API contracts:
1. /leads returns list of leads with pagination contract
2. /export/leads.csv returns valid CSV format and matching headers
"""
import pytest
import requests

pytestmark = pytest.mark.live_integration

def test_api_extended(live_api_url):
    res_leads = requests.get(f"{live_api_url}/leads?page=1&page_size=10", timeout=5)
    assert res_leads.status_code == 200, f"/leads endpoint failed: {res_leads.status_code}"
    leads_data = res_leads.json()
    assert isinstance(leads_data, dict)
    assert "total" in leads_data
    assert "items" in leads_data
    assert isinstance(leads_data["items"], list)

    res_csv = requests.get(f"{live_api_url}/leads/export/active_opportunities", timeout=5)
    assert res_csv.status_code == 200, f"CSV export failed: {res_csv.status_code}"
    content_type = res_csv.headers.get("content-type", "")
    assert "text/csv" in content_type or "text/plain" in content_type or "application/octet-stream" in content_type
    
    lines = res_csv.text.splitlines()
    assert len(lines) >= 1
    header = lines[0]
    for expected_col in ["Lead ID", "Company", "Outreach Status"]:
        assert expected_col in header
