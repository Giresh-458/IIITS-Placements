import os
import pytest
from fastapi.testclient import TestClient



@pytest.fixture
async def setup_db():
    from src.app.main import db_manager
    from src.storage.database import Base
    
    import uuid
    db_manager.db_url = f"sqlite+aiosqlite:///file:memdb_export_{uuid.uuid4().hex}?mode=memory&cache=shared"
    await db_manager.connect()

    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    yield db_manager
    
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await db_manager.disconnect()

@pytest.mark.asyncio
async def test_api_export_deterministic(setup_db):
    from src.app.main import app, db_manager
    client = TestClient(app)

    # Insert data into memory DB
    from src.storage.models.outreach import OutreachLead, OutreachContact
    async with db_manager.session_maker() as session:
        ev = OutreachLead(
            canonical_event_id="test1",
            company_name="TechCorp Solutions",
            role="SOFTWARE_ENGINEERING",
            temporal_status="HOT_OUTREACH_LEAD",
            outreach_priority="P1",
            contact_status="VERIFIED_RECRUITMENT_PHONE",
            outreach_readiness="READY",
            outreach_status="NOT_STARTED",
            snapshot_id="s1",
            currently_present=True
        )
        c = OutreachContact(
            contact_id="c1",
            company="TechCorp Solutions",
            phone="9876543210",
            contact_role="TALENT_ACQUISITION",
            verification_state="VERIFIED",
            confidence="HIGH",
            snapshot_id="s1"
        )
        session.add(ev)
        session.add(c)
        await session.commit()
    
    # Test Active Opportunities CSV
    response = client.get("/leads/export/active_opportunities")
    
    # Test Contacts CSV
    response = client.get("/leads/export/contacts")
    assert response.status_code == 200
    assert "9876543210" in response.text

    # Test Dashboard API (Leads List)
    response = client.get("/leads?outreach_status=NOT_STARTED")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(item["company_name"] == "TechCorp Solutions" for item in data["items"])
