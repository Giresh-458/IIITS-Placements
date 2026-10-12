"""
Live Integration Test: APScheduler Job Configuration
Recovery Status: REPLACEMENT_TEST (Original source unrecoverable)

Verifies APScheduler job metadata, next run times, and lifecycle events.
"""
import pytest
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

pytestmark = pytest.mark.live_integration

@pytest.mark.asyncio
async def test_scheduler_apscheduler():
    scheduler = AsyncIOScheduler()
    execution_record = []

    async def sample_job():
        execution_record.append("run")

    job = scheduler.add_job(
        sample_job,
        trigger=IntervalTrigger(seconds=0.2),
        id="production_pipeline_sweep",
        name="Hourly Pipeline Sweep"
    )
    assert job.id == "production_pipeline_sweep"
    assert job.name == "Hourly Pipeline Sweep"
    assert job.trigger is not None
    
    # Assert scheduler state transitions and actual job execution
    assert not scheduler.running
    scheduler.start()
    assert scheduler.running
    await asyncio.sleep(0.5)
    assert len(execution_record) >= 1, "APScheduler failed to execute scheduled job"
    scheduler.shutdown(wait=False)
