# Repository Map and Cleanup Baseline

This document records the execution paths visible in the current source tree. It is an inventory for cleanup and later stage acceptance, not a claim that every path is correct or production-ready.

## Repository hygiene rules

- `artifacts/crawl_seed_registry.json` and `artifacts/source_registry.json` are tracked inputs. Keep them unless a reviewed change explicitly replaces their purpose.
- Generated runtime files under `artifacts/` are ignored by Git. Do not commit live crawl results, local telemetry, or database reconciliation output as if they were source code.
- Use the current test command output as the source of truth; do not keep static test pass counts in documentation.
- Validation output must be derived from real artifacts or actual subprocess results. A printed statement is not proof that a browser fixture ran, that a process exited normally, or that Docker validation succeeded.
- Do not remove a legacy entry point merely because it looks duplicated. Check references, artifact contracts, and caller behavior before retirement.

## Execution entry points

### Orchestrated path

`src/orchestration/pipeline.py` defines `PipelineOrchestrator.run()`. The methods are executed in this order:

| Order | Stage | Current implementation observed |
|---:|---|---|
| 1 | Discovery | Uses an explicitly provided source list when supplied; otherwise reads `artifacts/crawl_seed_registry.json`. Validates record shape, HTTP(S) seed URLs, and budgets for crawlable P0 categories (`P0_DIRECT_EVENT_FEED`, `P0_PUBLIC_EVENT_ARCHIVE`, `P0_EVENT_INDEX_WITH_CHILD_DETAILS`). Fails closed if input is malformed or no crawlable sources are selected. |
| 2 | Crawling | Calls `CrawlerEngine.crawl_pages()` with bounded source limits and stores raw HTML/text page captures plus crawl telemetry; extraction is not performed in this stage. |
| 3 | Extraction | Calls `extract_candidates_from_pages()` over captured pages, scopes content to a primary article/body when identifiable, rejects likely multi-notice archives, and records extraction telemetry. |
| 4 | Normalization | Calls `normalize_candidates()` and writes `artifacts/normalized_hiring_events.json`. |
| 5 | Qualification | Calls `apply_business_filters()`, writes `artifacts/classified_events.json`, and uses a fixed `as_of` date in the current code. |
| 6 | Evidence | Currently a no-op method. |
| 7 | Contact Intelligence | Invokes `run_batch_7.py` as a subprocess and loads `normalized_contacts.json`. |
| 8 | Consolidation | Invokes `run_batch_8.py`, rejects failed or missing outputs, and loads validated outreach artifacts. |
| 9 | Persistence | Calls `Batch9Ingestion` directly with outreach lead/contact artifacts. |
| 10 | Change Detection | Currently a no-op method; change-detection behavior is called from persistence code. |

`scripts/run_pipeline.py` is a configuration/database-health utility. Its `health` command checks database connectivity, and `validate-config` checks configured limits. It does not invoke `PipelineOrchestrator.run()`.

### Standalone script path

The root-level scripts form a separate artifact-driven path, with separate assumptions and some overlapping outputs:

1. `scripts/verify_sources.py` refreshes `artifacts/crawl_seed_registry.json`.
2. `run_crawler.py` writes `discovered_events.json` and `crawl_telemetry.json`.
3. `run_recovery.py` rehydrates sources and writes `recovered_event_extractions.json`, `normalized_hiring_events.json`, evidence audit, and recovery telemetry.
4. `run_normalization.py` reads `recovered_event_extractions.json` and also writes `normalized_hiring_events.json`. This overlaps the output written by recovery; the intended order/ownership needs a later stage decision.
5. `run_batch_6.py` applies qualification and writes `classified_events.json`.
6. `run_batch_7.py` performs contact discovery/verification.
7. `run_batch_8.py` consolidates outreach artifacts.
8. `run_batch_9.py` ingests and reconciles the current lead/contact snapshot. Its final validation report currently writes `BATCH 9 = HOLD` unconditionally, even though the code calculates an `is_pass` value; the report is therefore not yet a usable GO signal.
9. `run_batch_10.py` also calls `Batch9Ingestion`; it is not currently an independent Change Detection implementation. Its report contains a static Docker-pass label, so that label must not be used as evidence of a Docker run.

`run_classification.py` is a legacy alternate classification script. Its expectations differ from the current return shape of `apply_business_filters()`; it is not the preferred Batch 6 reporting path while that contract mismatch remains.

## Known structural discrepancies to resolve during stage review

- The orchestrated path and standalone scripts are not the same execution path.
- The two tracked registries have different record shapes and source categories; do not treat them as interchangeable without a schema/ownership decision.
- Recovery and standalone normalization both write `normalized_hiring_events.json`.
- Extraction is a separate work unit after PR #10, but Evidence remains a no-op in the orchestrator.
- Change detection is embedded in persistence code in one path, while the standalone Batch 10 runner duplicates persistence behavior.
- Batch 9's final validation report currently hardcodes HOLD, while Batch 10's report hardcodes Docker validation as PASSED; neither line is reliable as acceptance evidence.
- The diagram-level logical stage count and the 10 named orchestrator methods have not been mapped one-to-one in the current repository documentation.

These discrepancies are intentionally recorded, not silently fixed here. Each will be addressed in the corresponding stage review so changes remain narrow and acceptance can be evidence-based.
