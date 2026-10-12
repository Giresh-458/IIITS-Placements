from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.storage.database import DatabaseManager

import os
import logging
logging.basicConfig(level=logging.INFO)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.orchestration.ingestion import Batch9Ingestion

db_manager = DatabaseManager()
scheduler = AsyncIOScheduler()

async def scheduled_ingestion():
    print("Starting scheduled pipeline run", flush=True)
    try:
        from src.orchestration.pipeline import PipelineOrchestrator
        orchestrator = PipelineOrchestrator(db_manager)
        final_state = await orchestrator.run()
        print(f"Scheduled pipeline result: {final_state['telemetry']}", flush=True)
    except Exception as e:
        print(f"Scheduled pipeline failed: {e}", flush=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_manager.connect()
    
    if os.environ.get("ENABLE_SCHEDULED_CRAWLS", "false").lower() == "true":
        interval_seconds = int(os.environ.get("SCHEDULER_INTERVAL_SECONDS", 3600))
        scheduler.add_job(scheduled_ingestion, 'interval', seconds=interval_seconds)
        scheduler.start()
        print("APScheduler started", flush=True)
        
    yield
    
    if scheduler.running:
        scheduler.shutdown()
    await db_manager.disconnect()

app = FastAPI(title="Placement Intelligence API", version="0.1.0", lifespan=lifespan)

from src.api.routes import leads, alerts, metrics
app.include_router(leads.router)
app.include_router(alerts.router, prefix="/alerts")
app.include_router(metrics.router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/version")
async def get_version():
    return {"version": "0.1.0"}

@app.get("/health/db")
async def db_health_check():
    is_healthy = await db_manager.check_health()
    return {"status": "ok" if is_healthy else "error"}

