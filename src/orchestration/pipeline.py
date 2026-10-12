import logging
import traceback
from datetime import datetime
from typing import Dict, Any, List
from src.orchestration.state import PipelineRunState, create_initial_state

logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    def __init__(self, db_manager=None):
        self.db_manager = db_manager

    async def _safe_execute(self, state: PipelineRunState, stage_name: str, func) -> PipelineRunState:
        state["current_stage"] = stage_name
        try:
            return await func(state)
        except Exception as e:
            logger.error(f"Error in {stage_name}: {e}")
            logger.error(traceback.format_exc())
            state["errors"].append({"stage": stage_name, "error": str(e)})
            state["terminal_status"] = "FAILED"
            state["stop_reason"] = f"Failed at {stage_name}: {str(e)}"
            return state

    async def _node_discovery(self, state: PipelineRunState):
        return await self._safe_execute(state, "DISCOVERY", self._do_discovery)

    async def _do_discovery(self, state: PipelineRunState):
        import json
        with open('artifacts/crawl_seed_registry.json', 'r') as f:
            seeds = json.load(f)
        state["sources"] = [s for s in seeds if s.get("source_category") == "P0_DIRECT_EVENT_FEED"]
        if not state["sources"]:
            logger.info("No sources provided to pipeline.")
            state["stop_reason"] = "No sources configured"
        state["telemetry"]["sources_attempted"] = len(state["sources"])
        return state

    async def _do_crawling(self, state: PipelineRunState):
        from src.crawler.engine import CrawlerEngine
        engine = CrawlerEngine(state["sources"], max_pages=3, max_depth=1)
        events, telemetry = await engine.run()
        state["crawl_telemetry"] = telemetry.model_dump(mode='json')
        state["telemetry"]["crawl_telemetry"] = state["crawl_telemetry"]
        state["raw_candidates"] = [e.model_dump(mode='json') for e in events]
        state["telemetry"]["sources_succeeded"] = telemetry.sources_attempted
        state["telemetry"]["urls_fetched"] = telemetry.pages_attempted
        state["telemetry"]["http_requests"] = telemetry.http_requests
        state["telemetry"]["browser_pages"] = telemetry.browser_pages
        return state

    async def _do_extraction(self, state: PipelineRunState):
        # Already handled by CrawlerEngine in existing implementation
        state["telemetry"]["extraction_candidates"] = len(state["raw_candidates"])
        return state

    async def _do_normalization(self, state: PipelineRunState):
        from src.orchestration.normalization_adapter import normalize_candidates
        from src.models.domain import HiringEventCandidate
        candidates = []
        import pydantic
        for c in state["raw_candidates"]:
            try:
                candidates.append(HiringEventCandidate(**c))
            except pydantic.ValidationError as e:
                logger.warning(f"Quarantining malformed event: {e}")
                state["errors"].append(f"Malformed event quarantined: {str(e)}")
                
        normalized = normalize_candidates(candidates)
        state["normalized_events"] = [e.model_dump(mode='json') for e in normalized]
        state["telemetry"]["normalized_events"] = len(normalized)
        import json
        with open('artifacts/normalized_hiring_events.json', 'w', encoding='utf-8') as f:
            json.dump(state["normalized_events"], f, indent=2)
        return state

    async def _do_qualification(self, state: PipelineRunState):
        from src.classification.business_rules import apply_business_filters
        from src.models.domain import NormalizedHiringEvent
        import json
        events = [NormalizedHiringEvent(**item) for item in state["normalized_events"]]
        res = apply_business_filters(events, as_of=datetime(2026, 10, 5))
        classifications = res["classifications"]
        
        classified_data = []
        qualified_only = []
        rejected_only = []
        for ev in events:
            ev_dict = ev.dict()
            cls = classifications[ev.event_id]
            ev_dict["business_classification"] = cls.__dict__
            classified_data.append(ev_dict)
            if cls.target_fit == "FILTERED_OUT":
                state["telemetry"]["rejected_events"] += 1
                rejected_only.append(ev_dict)
            else:
                state["telemetry"]["qualified_events"] += 1
                qualified_only.append(ev_dict)
                
        state["qualified_events"] = qualified_only
        state["rejected_events"] = rejected_only
        with open('artifacts/classified_events.json', 'w', encoding='utf-8') as f:
            json.dump(classified_data, f, indent=2)
        return state

    async def _do_evidence(self, state: PipelineRunState):
        # Evidence is inherently populated in previous stages
        return state

    async def _do_contact_intelligence(self, state: PipelineRunState):
        import subprocess
        # Rely on run_batch_7 for bounded discovery
        res = subprocess.run("python run_batch_7.py", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            logger.warning(f"Contact Intelligence failed: {res.stderr}")
        import json
        try:
            with open('artifacts/normalized_contacts.json', 'r', encoding='utf-8') as f:
                state["contacts"] = json.load(f)
        except:
            state["contacts"] = []
        return state

    async def _do_consolidation(self, state: PipelineRunState):
        import subprocess
        res = subprocess.run("python run_batch_8.py", shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            logger.warning(f"Consolidation failed: {res.stderr}")
        import json
        try:
            with open('artifacts/outreach_leads.json', 'r', encoding='utf-8') as f:
                state["consolidated_leads"] = json.load(f)
            state["telemetry"]["consolidated_leads"] = len(state["consolidated_leads"])
        except:
            state["consolidated_leads"] = []
        return state

    async def _do_persistence(self, state: PipelineRunState):
        from src.orchestration.ingestion import Batch9Ingestion
        import json
        
        ingester = Batch9Ingestion(self.db_manager)
        leads_path = "artifacts/outreach_leads.json"
        contacts_path = "artifacts/outreach_contacts.json"
        
        # In Batch 11 we reuse Batch 9 persistence exactly.
        # But if the file doesn't exist, we write what we have in state.
        if not __import__('os').path.exists(leads_path):
            with open(leads_path, "w") as f:
                json.dump(state["consolidated_leads"], f)
        if not __import__('os').path.exists(contacts_path):
            with open(contacts_path, "w") as f:
                json.dump(state["contacts"], f)
                
        try:
            res = await ingester.ingest_snapshot(leads_path, contacts_path)
            state["persistence_result"] = res
            state["snapshot_id"] = res.get("snapshot_id")
            state["telemetry"]["persistence_inserts"] = res.get("inserted", 0)
            state["telemetry"]["persistence_updates"] = res.get("updated", 0)
            state["telemetry"]["persistence_unchanged"] = res.get("unchanged", 0)
            state["telemetry"]["alerts_generated"] = res.get("alerts_generated", 0)
        except Exception as e:
            state["errors"].append({"stage": "PERSISTENCE", "error": str(e)})
            state["terminal_status"] = "FAILED"
            state["stop_reason"] = "Ingestion Error"
        return state

    async def _do_change_detection(self, state: PipelineRunState):
        # Already handled inside Batch9Ingestion!
        return state

    async def _node_completed(self, state: PipelineRunState):
        state["current_stage"] = "COMPLETED"
        if state.get("errors"):
            state["terminal_status"] = "PARTIAL_SUCCESS"
        elif state.get("terminal_status") != "FAILED":
            state["terminal_status"] = "SUCCESS"
            
        state["completed_at"] = datetime.utcnow().isoformat()
        start = datetime.fromisoformat(state["started_at"])
        end = datetime.fromisoformat(state["completed_at"])
        state["telemetry"]["total_duration_seconds"] = (end - start).total_seconds()
        state["telemetry"]["completed_at"] = state["completed_at"]
        state["telemetry"]["terminal_status"] = state["terminal_status"]
        
        logger.info(f"Pipeline {state['run_id']} completed with status: {state['terminal_status']}")
        self._persist_run(state)
        return state

    async def _node_failed(self, state: PipelineRunState):
        state["current_stage"] = "FAILED"
        state["completed_at"] = datetime.utcnow().isoformat()
        
        start = datetime.fromisoformat(state["started_at"])
        end = datetime.fromisoformat(state["completed_at"])
        state["telemetry"]["total_duration_seconds"] = (end - start).total_seconds()
        state["telemetry"]["completed_at"] = state["completed_at"]
        state["telemetry"]["terminal_status"] = "FAILED"
        state["telemetry"]["stop_reason"] = state.get("stop_reason")
        
        logger.error(f"Pipeline {state['run_id']} failed: {state['stop_reason']}")
        self._persist_run(state)
        return state

    def _persist_run(self, state: PipelineRunState):
        import json
        import os
        try:
            run_record = {
                "run_id": state["run_id"],
                "started_at": state["started_at"],
                "completed_at": state["completed_at"],
                "terminal_status": state.get("terminal_status", "UNKNOWN"),
                "stop_reason": state.get("stop_reason"),
                "telemetry": state.get("telemetry", {}),
                "errors": state.get("errors", [])
            }
            with open('artifacts/run_history.jsonl', 'a', encoding='utf-8') as f:
                f.write(json.dumps(run_record) + "\n")
        except Exception as e:
            logger.error(f"Failed to persist run history: {e}")

    async def run(self, sources: List[Dict[str, Any]] = None) -> PipelineRunState:
        state = create_initial_state(sources=sources)
        
        stages = [
            ("DISCOVERY", self._do_discovery),
            ("CRAWLING", self._do_crawling),
            ("EXTRACTION", self._do_extraction),
            ("NORMALIZATION", self._do_normalization),
            ("QUALIFICATION", self._do_qualification),
            ("EVIDENCE", self._do_evidence),
            ("CONTACT_INTELLIGENCE", self._do_contact_intelligence),
            ("CONSOLIDATION", self._do_consolidation),
            ("PERSISTENCE", self._do_persistence),
            ("CHANGE_DETECTION", self._do_change_detection)
        ]
        
        for stage_name, stage_func in stages:
            if state["terminal_status"] == "FAILED":
                break
            state = await self._safe_execute(state, stage_name, stage_func)
            
        if state["terminal_status"] == "FAILED":
            state = await self._node_failed(state)
        else:
            state = await self._node_completed(state)
            
        return state
