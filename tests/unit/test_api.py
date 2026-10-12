import pytest
import json
from httpx import AsyncClient, ASGITransport
from src.app.main import app, db_manager

@pytest.fixture
async def temp_db():
    db_manager.db_url = "sqlite+aiosqlite:///:memory:"
    await db_manager.connect()
    from src.storage.models.outreach import Base
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield db_manager
    await db_manager.disconnect()

@pytest.mark.asyncio
async def test_health_endpoints(temp_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        
        response = await client.get("/health/db")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_lead_list_pagination(temp_db):
    from src.storage.models.outreach import OutreachLead
    async with db_manager.session_maker() as session:
        for i in range(5):
            lead = OutreachLead(
                canonical_event_id=f"test_event_{i}",
                company_name=f"Company {i}",
                branches=json.dumps([]),
                outreach_priority="P2",
                outreach_readiness="READY",
                contact_status="NO_VERIFIED_PHONE",
                verified_contact_ids=json.dumps([]),
                source_lineage=json.dumps({}),
                snapshot_id="snap1"
            )
            session.add(lead)
        await session.commit()
        
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/leads?page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        
        response = await client.get("/leads?company=Company 3")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["company_name"] == "Company 3"

@pytest.mark.asyncio
async def test_stats_and_exports(temp_db):
    from src.storage.models.outreach import OutreachLead
    async with db_manager.session_maker() as session:
        for i in range(2):
            lead = OutreachLead(
                canonical_event_id=f"export_test_event_{i}",
                company_name=f"ExpCompany {i}",
                branches=json.dumps([]),
                temporal_status="ACTIVE_OPPORTUNITY",
                outreach_priority="P2",
                outreach_readiness="READY",
                contact_status="NO_VERIFIED_PHONE",
                verified_contact_ids=json.dumps([]),
                source_lineage=json.dumps({"event_id": f"e{i}"}),
                snapshot_id="snap1"
            )
            session.add(lead)
        await session.commit()
        
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/leads/stats/summary")
        assert res.status_code == 200
        data = res.json()
        assert data["total_leads"] >= 2
        assert "P2" in data["by_priority"]
        
        res = await client.get("/leads/export/active_opportunities")
        assert res.status_code == 200
        assert "ExpCompany 0" in res.text
        assert "ExpCompany 1" in res.text
