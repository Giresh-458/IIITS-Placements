# Placement Intelligence Agent

A self-hosted, evidence-backed platform for college placement intelligence, hiring event extraction, and recruiter outreach discovery. Configured with a default target profile for IIIT Sri City (CSE/ECE programs).

## 1. Problem Addressed

College placement notifications and campus recruitment updates across Indian technical institutions are fragmented across unstructured formats—dynamic web portals, HTML noticeboards, CMS tables, and scanned or text PDFs. 

The Placement Intelligence Agent automates:
- Monitoring and discovery of hiring event notices across targeted institutional portals.
- Deterministic extraction and normalization of company names, roles, compensation (CTC), eligibility criteria (branch, graduation batch, CGPA), and deadlines.
- Bounded recruiter contact intelligence and phone verification without external fabrication.
- Lead qualification matching institutional criteria (e.g., minimum CTC cutoffs and freshness windows).
- Idempotent PostgreSQL persistence with automated schema migrations, snapshot immutability, and change-detection alerting.

## 2. Capabilities & Components

- **Source Discovery & Ingestion**: Bounded web crawler supporting static HTML, JavaScript rendering (Playwright), and PDF document parsing.
- **Extraction & Normalization**: Structural regex extraction, company name sanitization, compensation parsing (LPA, stipends), and branch/role classification.
- **Business Rules Qualification**: Freshness evaluation (15-day window), branch eligibility (CSE/ECE), and compensation threshold filtering (CSE: 10.0 LPA, ECE: 6.5 LPA).
- **Contact Intelligence & Verification**: Structured telephone extraction with country code standardization, verification state tracking, and confidence scoring.
- **Pipeline Orchestration**: LangGraph-inspired stateful pipeline (`src/orchestration/pipeline.py`) coordinating discovery through persistence.
- **Persistence & Auditing**: PostgreSQL relational backend via SQLAlchemy (asyncpg) with Alembic schema versioning, source-truth immutability, and append-only audit logging.
- **REST API**: FastAPI service exposing leads, stats, health checks, alerts, and CSV exports.
- **Analytics Dashboard**: Streamlit web dashboard (`src/dashboard/app.py`) for outreach lead exploration and source telemetry.

## 3. Technology Stack

- **Runtime**: Python 3.11+
- **Web API**: FastAPI, Uvicorn
- **Database**: PostgreSQL 15+, SQLAlchemy 2.0 (asyncpg), Alembic
- **Testing & SQLite**: pytest, pytest-asyncio, aiosqlite
- **Crawling & Scraping**: Crawlee, Playwright, HTTPX, BeautifulSoup4
- **Document Processing**: pypdf, python-dateutil
- **UI Dashboard**: Streamlit, Pandas
- **Containers**: Docker, Docker Compose

## 4. Setup & Installation

### Prerequisites
- Python 3.11 or higher
- PostgreSQL 15+ (local or via Docker)

### Installation
1. Clone the repository and navigate to the project root:
   ```bash
   git clone https://github.com/Giresh-458/IIITS-Placements.git
   cd IIITS-Placements
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install --with-deps chromium
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to configure your PostgreSQL credentials, Ollama endpoint, and crawl budget limits.

## 5. Configuration & Environment Variables

Key settings configured via `.env` (referenced in `.env.example`):

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy async connection string | `postgresql+asyncpg://user:password@localhost:5432/placement_db` |
| `POSTGRES_USER` | PostgreSQL database user | `user` |
| `POSTGRES_PASSWORD` | PostgreSQL user password | `password` |
| `POSTGRES_DB` | PostgreSQL database name | `placement_db` |
| `SCHEDULER_INTERVAL_SECONDS` | Ingestion scheduler polling interval | `5` |
| `ENABLE_SCHEDULED_CRAWLS` | Feature flag for autonomous scheduled crawls | `false` |
| `CSE_MIN_LPA` | Minimum CTC threshold for CSE qualification | `10.0` |
| `ECE_MIN_LPA` | Minimum CTC threshold for ECE qualification | `6.5` |
| `RECENT_EVENT_DAYS_WINDOW` | Freshness window for event qualification (days) | `15` |
| `MAX_RUNTIME_SECONDS` | Maximum crawl execution budget | `3600` |
| `OLLAMA_ENDPOINT` | Local Ollama LLM service endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL` | LLM model for extraction assistance | `llama3` |

## 6. Database Migrations

Apply Alembic migrations to set up or update the PostgreSQL database schema:

```bash
# Upgrade to head schema
alembic upgrade head

# Downgrade to base schema
alembic downgrade base
```

## 7. Running the Application

### Running the API
```bash
uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload
```
API endpoints documentation will be available at `http://localhost:8000/docs`.

### Running the Dashboard
```bash
streamlit run src/dashboard/app.py
```

### Current execution paths (important)

The repository currently has two execution surfaces that have **not yet been certified as equivalent**:

- The standalone scripts listed below exchange JSON artifacts under `artifacts/`.
- `src/orchestration/pipeline.py` defines a separate `PipelineOrchestrator.run()` path.
- `scripts/run_pipeline.py` currently provides only `health` and `validate-config` commands; it does not invoke `PipelineOrchestrator.run()`.

Do not treat a successful standalone script or a single orchestrator test as an end-to-end pipeline certification. The stage-by-stage review will reconcile these execution paths before a full pipeline run. A detailed code-level inventory is maintained in [`docs/repository_map.md`](docs/repository_map.md).

### Standalone script inventory

| Purpose | Entry point | Main output or behavior |
|---|---|---|
| Verify source portals and refresh the crawl seed registry | `python scripts/verify_sources.py` | Writes `artifacts/crawl_seed_registry.json` |
| Crawl configured seed pages | `python run_crawler.py` | Writes `artifacts/discovered_events.json` and `artifacts/crawl_telemetry.json` |
| Rehydrate source evidence and recover event fields | `python run_recovery.py` | Writes recovered extractions, normalized events, evidence audit, and recovery telemetry |
| Normalize recovered extractions | `python run_normalization.py` | Reads `recovered_event_extractions.json` and writes `normalized_hiring_events.json` |
| Apply business qualification and produce a report | `python run_batch_6.py` | Writes `classified_events.json` and a Batch 6 report |
| Discover and verify recruiter contacts | `python run_batch_7.py` | Writes normalized contacts and Batch 7 artifacts |
| Consolidate outreach leads and contacts | `python run_batch_8.py` | Writes outreach lead/contact artifacts and Batch 8 validation output |
| Persist and reconcile the current snapshot | `python run_batch_9.py` | Writes Batch 9 persistence reports; requires the configured database |
| Legacy persistence runner | `python run_batch_10.py` | Also calls `Batch9Ingestion`; it is not currently an independent Change Detection implementation |

`run_classification.py` is an additional legacy classification entry point and is not listed as the preferred runner because its expected result shape differs from the current `apply_business_filters` interface. Use `run_batch_6.py` for the existing Batch 6 report path while that mismatch is reviewed.

Runtime outputs in `artifacts/` are ignored by Git. The two committed registry JSON files are source/configuration inputs and are intentionally retained.

### Repository health and validation tools

- `python scripts/run_pipeline.py validate-config` checks configured crawl budgets and eligibility thresholds.
- `python scripts/run_pipeline.py health` checks database connectivity only; it does not run the crawler or the pipeline.
- `python run_validation.py` validates the available source registry, discovered-event, and crawl-telemetry artifacts. It reports recorded telemetry but does not fabricate a crawler exit code or claim browser tests were run.
- `python run_final_tests.py` runs the default pytest suite and returns pytest's exit code. It does not execute a persistence script.

### Docker Deployment
Start API and PostgreSQL services in isolated containers:
```bash
docker compose up -d
```

## 8. Test Suite & Validation

Test counts are deliberately not recorded here because they become stale when a branch changes. Use the current checkout's terminal output as the source of truth.

### Deterministic tests
```bash
python -m pytest tests/deterministic -q
```

### Unit tests
```bash
python -m pytest tests/unit -q
```

### Default test suite
The default pytest configuration excludes tests marked `live_integration`:
```bash
python -m pytest
```
The equivalent repository helper is `python run_final_tests.py`; it propagates the test process exit code and does not run database-ingestion scripts as part of testing.

### Live integration tests
These require the documented live services:
```bash
python -m pytest tests/live_integration -m "live_integration"
```

## 9. Current Known Limitations

- **Execution paths need reconciliation**: the standalone scripts and `PipelineOrchestrator.run()` are separate paths and have not yet been accepted as equivalent. See the execution-path notes above.
- **Live infrastructure dependency**: live integration tests require configured services; their actual results must be collected from the environment in which they run.
- **Pipeline acceptance is stage-based**: no full end-to-end GO decision should be inferred from unit tests alone.
