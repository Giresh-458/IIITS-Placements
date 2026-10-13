
import pytest
from src.storage.database import DatabaseManager
from src.orchestration.pipeline import PipelineOrchestrator
from src.storage.database import Base
from sqlalchemy import text
import os

@pytest.fixture
async def setup_db():
    import uuid
    db_url = f"sqlite+aiosqlite:///file:memdb_{uuid.uuid4().hex}?mode=memory&cache=shared"
    db = DatabaseManager(db_url=db_url)
    await db.connect()
    async with db.engine.begin() as conn:
        from src.storage.models.outreach import OutreachLead, OutreachContact, SnapshotMetadata
        from src.storage.models.alerts import SystemAlert
        await conn.run_sync(Base.metadata.create_all)
    return db

@pytest.mark.asyncio
async def test_end_to_end_replay(setup_db):
    db = setup_db
    orchestrator = PipelineOrchestrator(db)
    
    async def mock_crawl(state):
        state['crawl_telemetry'] = {}
        state['telemetry']['crawl_telemetry'] = {}
        page_text = (
            "Campus Recruitment Drive by Valid Corp Int. "
            "Role: SDE. CTC: 10 LPA. Batch 2026. Branches: CSE, IT"
        )
        state['crawled_pages'] = [{
            'institution': 'Inst1',
            'seed_url': 'http://test1',
            'url': 'http://test1/event',
            'html': f"<html><body>{page_text}</body></html>",
            'text': page_text,
            'depth': 0,
            'http_status': 200,
        }]
        state['raw_candidates'] = []
        state['telemetry']['sources_succeeded'] = 1
        state['telemetry']['sources_attempted'] = 1
        return state
        
    orchestrator._do_crawling = mock_crawl
    
    # Run 1
    state1 = await orchestrator.run()
    assert state1['terminal_status'] in ['SUCCESS', 'PARTIAL_SUCCESS']
    run1_canonical_ids = [ev.get('event_id') for ev in state1.get('qualified_events', [])]
    run1_alerts = state1.get('telemetry', {}).get('alerts_generated', 0)
    assert state1['telemetry']['persistence_inserts'] == 1
    assert state1['telemetry']['persistence_updates'] == 0
    
    # Run 2 (Replay with same data)
    state2 = await orchestrator.run()
    assert state2['terminal_status'] in ['SUCCESS', 'PARTIAL_SUCCESS']
    run2_canonical_ids = [ev.get('event_id') for ev in state2.get('qualified_events', [])]
    run2_new_inserts = state2['telemetry']['persistence_inserts']
    assert state2['telemetry']['persistence_updates'] == 1
    
    # Check duplicate business alerts (e.g. no new lead alerts on replay)
    # On replay of unchanged event, 0 NEW_LEAD alerts are created
    new_lead_alerts_run2 = [a for a in state2.get('alerts', []) if a.get('alert_type') == 'NEW_LEAD']
    run2_duplicate_business_alerts = len(new_lead_alerts_run2)
    
    print(f"\n[REPLAY_VERIFICATION] run1_canonical_ids: {run1_canonical_ids}")
    print(f"[REPLAY_VERIFICATION] run2_canonical_ids: {run2_canonical_ids}")
    print(f"[REPLAY_VERIFICATION] run2_new_inserts: {run2_new_inserts}")
    print(f"[REPLAY_VERIFICATION] run2_duplicate_business_alerts: {run2_duplicate_business_alerts}")
    
    assert run1_canonical_ids == run2_canonical_ids
    assert run2_new_inserts == 0
    assert run2_duplicate_business_alerts == 0
    
    # Verify DB only has 1 lead
    async with db.session_maker() as session:
        leads_count = await session.execute(text('SELECT COUNT(*) FROM outreach_leads;'))
        assert leads_count.scalar() == 1
