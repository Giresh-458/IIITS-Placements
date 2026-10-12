from fastapi import APIRouter, Depends, HTTPException
import json
import os

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/runs")
async def list_runs():
    runs = []
    try:
        with open("artifacts/run_history.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    runs.append(json.loads(line))
        return runs[::-1] # Newest first
    except Exception as e:
        return []

@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    try:
        with open("artifacts/run_history.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    run = json.loads(line)
                    if run.get("run_id") == run_id:
                        return run
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="Run not found")

@router.get("/telemetry")
async def get_telemetry():
    runs = await list_runs()
    if not runs:
        return {}
    return runs[0].get("telemetry", {})

@router.get("/sources/health")
async def get_source_health():
    # Read configured sources
    sources = []
    try:
        with open("artifacts/crawl_seed_registry.json", "r", encoding="utf-8") as f:
            sources = json.load(f)
    except:
        return []
    
    # We could augment this with the latest crawl telemetry if we saved it globally,
    # or just return the sources and let the dashboard join it with the latest run telemetry.
    # The latest run telemetry contains `source_stats`.
    latest_run = None
    runs = await list_runs()
    if runs:
        latest_run = runs[0]
        
    health_data = []
    for s in sources:
        h = {
            "source_category": s.get("source_category"),
            "institution": s.get("institution"),
            "seed_url": s.get("seed_url"),
            "priority": s.get("priority", "UNKNOWN"),
            "health": "UNKNOWN",
            "last_success": None,
            "last_failure": None,
            "events_found": 0,
            "pages_visited": 0,
            "stop_reason": None
        }
        
        if latest_run and "crawl_telemetry" in latest_run.get("telemetry", {}):
            crawl_tel = latest_run["telemetry"]["crawl_telemetry"]
            if isinstance(crawl_tel, str):
                try:
                    crawl_tel = json.loads(crawl_tel)
                except:
                    pass
            if isinstance(crawl_tel, dict):
                source_stats = crawl_tel.get("source_stats", {})
                if s.get("institution") in source_stats:
                    st = source_stats[s.get("institution")]
                    h["pages_visited"] = st.get("pages_visited", 0)
                    h["events_found"] = st.get("events_found", 0)
                    h["stop_reason"] = st.get("stop_reason")
                    
                    if h["stop_reason"] in ["BUDGET_EXHAUSTED", None]:
                        h["health"] = "HEALTHY"
                    elif h["stop_reason"] in ["BLOCKED_OR_FORBIDDEN"]:
                        h["health"] = "BLOCKED_OR_FORBIDDEN"
                        h["last_failure"] = latest_run["completed_at"]
                    elif h["stop_reason"] in ["AUTHENTICATION_REQUIRED"]:
                        h["health"] = "DEGRADED"
                    else:
                        h["health"] = "FAILED"
                        h["last_failure"] = latest_run["completed_at"]
                        
                    if h["health"] == "HEALTHY":
                        h["last_success"] = latest_run["completed_at"]
        
        health_data.append(h)
    
    return health_data
