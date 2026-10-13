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
        from pathlib import Path
        from urllib.parse import urlparse

        supported_categories = {
            "P0_DIRECT_EVENT_FEED",
            "P0_PUBLIC_EVENT_ARCHIVE",
            "P0_EVENT_INDEX_WITH_CHILD_DETAILS",
        }

        if state.get("sources_override_provided", False):
            seeds = state["sources"]
            registry_description = "provided source override"
        else:
            registry_path = Path("artifacts/crawl_seed_registry.json")
            try:
                with registry_path.open("r", encoding="utf-8") as registry_file:
                    seeds = json.load(registry_file)
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    f"Could not load discovery registry {registry_path}: {exc}"
                ) from exc
            registry_description = str(registry_path)

        if not isinstance(seeds, list):
            raise RuntimeError(
                f"Discovery input from {registry_description} must be a JSON list."
            )

        selected_sources = []
        for index, seed in enumerate(seeds):
            if not isinstance(seed, dict):
                raise RuntimeError(
                    f"Discovery source record {index} in {registry_description} "
                    "must be a JSON object."
                )

            for field in ("institution", "seed_url", "source_category"):
                value = seed.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise RuntimeError(
                        f"Discovery source record {index} in {registry_description} "
                        f"requires a non-empty {field!r}."
                    )

            parsed_url = urlparse(seed["seed_url"])
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
                raise RuntimeError(
                    f"Discovery source record {index} has an invalid HTTP(S) "
                    f"seed_url: {seed['seed_url']!r}."
                )

            if seed["source_category"] in supported_categories:
                limits = seed.get("crawl_limits", {})
                if not isinstance(limits, dict):
                    raise RuntimeError(
                        f"Discovery source record {index} crawl_limits must be an object."
                    )

                max_pages = limits.get("max_pages", 3)
                max_depth = limits.get("max_depth", 1)
                if (
                    isinstance(max_pages, bool)
                    or not isinstance(max_pages, int)
                    or max_pages < 1
                ):
                    raise RuntimeError(
                        f"Discovery source record {index} max_pages must be a positive integer."
                    )
                if (
                    isinstance(max_depth, bool)
                    or not isinstance(max_depth, int)
                    or max_depth < 0
                ):
                    raise RuntimeError(
                        f"Discovery source record {index} max_depth must be a non-negative integer."
                    )
                selected_sources.append(seed)

        if not selected_sources:
            raise RuntimeError(
                "Discovery found no crawlable sources in "
                f"{registry_description}; refusing to continue with an empty crawl."
            )

        state["sources"] = selected_sources
        state["telemetry"]["sources_attempted"] = len(selected_sources)
        state["stop_reason"] = None
        return state

    async def _do_crawling(self, state: PipelineRunState):
        from src.crawler.engine import CrawlerEngine

        engine = CrawlerEngine(state["sources"], max_pages=3, max_depth=1)
        events, telemetry = await engine.run()
        state["crawl_telemetry"] = telemetry.model_dump(mode="json")
        state["telemetry"]["crawl_telemetry"] = state["crawl_telemetry"]
        state["raw_candidates"] = [event.model_dump(mode="json") for event in events]

        # Attempted sources are not necessarily successful sources.
        state["telemetry"]["sources_succeeded"] = telemetry.sources_succeeded
        state["telemetry"]["sources_failed"] = telemetry.sources_failed
        state["telemetry"]["urls_fetched"] = telemetry.pages_attempted
        state["telemetry"]["http_requests"] = telemetry.http_requests
        state["telemetry"]["browser_pages"] = telemetry.browser_pages
        state["telemetry"]["exceptions"] = len(telemetry.exceptions)
        state["failed_sources"] = [
            {
                "institution": institution,
                "stop_reason": stats.get("stop_reason"),
                "pages_attempted": stats.get("pages_visited", 0),
                "pages_succeeded": stats.get("pages_succeeded", 0),
            }
            for institution, stats in telemetry.source_stats.items()
            if stats.get("pages_succeeded", 0) == 0
        ]

        if telemetry.sources_failed:
            state["warnings"].append(
                f"Crawling: {telemetry.sources_failed} of "
                f"{telemetry.sources_attempted} eligible sources had no successful page."
            )
        if telemetry.pages_failed:
            state["warnings"].append(
                f"Crawling: {telemetry.pages_failed} page request(s) failed."
            )

        if telemetry.sources_attempted > 0 and telemetry.sources_succeeded == 0:
            raise RuntimeError(
                f"Crawling failed for all {telemetry.sources_attempted} eligible sources."
            )
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
        import json
        import subprocess
        import sys
        from pathlib import Path

        # Batch 7 owns this output. Remove a previous run's artifact before
        # starting so a failed or incomplete execution cannot reuse stale data.
        contacts_path = Path("artifacts/normalized_contacts.json")
        try:
            contacts_path.unlink(missing_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"Could not remove previous Batch 7 output {contacts_path}: {exc}"
            ) from exc

        res = subprocess.run(
            [sys.executable, "run_batch_7.py"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            details = "\n".join(
                part.strip() for part in (res.stderr, res.stdout) if part and part.strip()
            )
            raise RuntimeError(
                f"Batch 7 failed with exit code {res.returncode}: "
                f"{details or 'no stdout/stderr captured'}"
            )

        if not contacts_path.is_file():
            raise RuntimeError(
                "Batch 7 exited successfully but did not produce "
                f"{contacts_path}; refusing to continue with missing output."
            )

        with contacts_path.open("r", encoding="utf-8") as f:
            state["contacts"] = json.load(f)
        return state

    async def _do_consolidation(self, state: PipelineRunState):
        import json
        import subprocess
        import sys
        from pathlib import Path

        # Remove outputs from earlier runs before Batch 8 starts. This prevents
        # a failed run from silently reusing an old leads/contacts artifact.
        output_paths = [
            Path("artifacts/outreach_leads.json"),
            Path("artifacts/outreach_contacts.json"),
            Path("artifacts/outreach_telemetry.json"),
            Path("artifacts/batch_8_reconciliation.md"),
            Path("artifacts/batch_8_final_validation.md"),
        ]
        for output_path in output_paths:
            try:
                output_path.unlink(missing_ok=True)
            except OSError as exc:
                raise RuntimeError(
                    f"Could not remove previous Batch 8 output {output_path}: {exc}"
                ) from exc

        res = subprocess.run(
            [sys.executable, "run_batch_8.py"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            details = "\n".join(
                part.strip() for part in (res.stderr, res.stdout) if part and part.strip()
            )
            raise RuntimeError(
                f"Batch 8 failed with exit code {res.returncode}: "
                f"{details or 'no stdout/stderr captured'}"
            )

        required_paths = [
            Path("artifacts/outreach_leads.json"),
            Path("artifacts/outreach_contacts.json"),
            Path("artifacts/outreach_telemetry.json"),
            Path("artifacts/batch_8_final_validation.md"),
        ]
        missing_paths = [str(path) for path in required_paths if not path.is_file()]
        if missing_paths:
            raise RuntimeError(
                "Batch 8 exited successfully but did not produce required fresh "
                f"artifacts: {', '.join(missing_paths)}"
            )

        validation_report = Path("artifacts/batch_8_final_validation.md").read_text(
            encoding="utf-8"
        )
        if "BATCH 8 = PASS" not in validation_report:
            raise RuntimeError(
                "Batch 8 exited successfully but its final validation report "
                "does not contain 'BATCH 8 = PASS'."
            )

        with Path("artifacts/outreach_leads.json").open("r", encoding="utf-8") as f:
            leads = json.load(f)
        with Path("artifacts/outreach_contacts.json").open("r", encoding="utf-8") as f:
            contacts = json.load(f)
        with Path("artifacts/outreach_telemetry.json").open("r", encoding="utf-8") as f:
            batch_8_telemetry = json.load(f)

        if not isinstance(leads, list):
            raise RuntimeError("Batch 8 outreach_leads.json must contain a JSON list.")
        if not isinstance(contacts, list):
            raise RuntimeError("Batch 8 outreach_contacts.json must contain a JSON list.")
        if not isinstance(batch_8_telemetry, dict):
            raise RuntimeError("Batch 8 outreach_telemetry.json must contain a JSON object.")
        if batch_8_telemetry.get("exceptions", 0) != 0:
            raise RuntimeError(
                "Batch 8 validation passed but telemetry reports exceptions: "
                f"{batch_8_telemetry.get('exceptions')}"
            )

        state["consolidated_leads"] = leads
        state["telemetry"]["consolidated_leads"] = len(leads)
        state["telemetry"]["batch_8_telemetry"] = batch_8_telemetry
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
