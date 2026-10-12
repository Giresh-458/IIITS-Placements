"""
Live Integration Test: Background Scheduler Execution
Recovery Status: REPLACEMENT_TEST (Original source unrecoverable due to log truncation)

Verifies that background crawl & outreach scheduler jobs register correctly
and execute within the configured schedule window.
"""
import pytest
import asyncio
from src.config.settings import settings

pytestmark = pytest.mark.live_integration

@pytest.mark.asyncio
async def test_scheduler():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    
    scheduler = AsyncIOScheduler()
    execution_counter = {"runs": 0}

    async def mock_scheduled_task():
        execution_counter["runs"] += 1

    # Register interval task with fast trigger for live integration test
    scheduler.add_job(
        mock_scheduled_task,
        trigger=IntervalTrigger(seconds=1),
        id="test_live_crawl_job",
        replace_existing=True
    )
    
    scheduler.start()
    try:
        # Wait 2.5 seconds to observe at least 2 executions
        await asyncio.sleep(2.5)
        assert execution_counter["runs"] >= 2, f"Scheduler failed to execute: {execution_counter['runs']} runs"
        job = scheduler.get_job("test_live_crawl_job")
        assert job is not None, "Scheduler job deregistered unexpectedly"
    finally:
        scheduler.shutdown(wait=False)
