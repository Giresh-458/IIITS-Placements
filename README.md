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

### Running Pipeline Stages
- **Verify Portal Sources**: `python scripts/verify_sources.py`
- **Execute Crawler**: `python run_crawler.py`
- **Normalize Extractions**: `python run_normalization.py`
- **Apply Business Rules**: `python run_classification.py`
- **Lead Consolidation**: `python run_batch_8.py`
- **Database Ingestion**: `python run_batch_9.py`
- **Change Detection**: `python run_batch_10.py`

### Docker Deployment
Start API and PostgreSQL services in isolated containers:
```bash
docker compose up -d
```

## 8. Test Suite & Validation

The test suite separates deterministic offline tests from tests requiring live external infrastructure.

### Deterministic Tests (Offline / In-Memory)
Requires no running PostgreSQL or external services:
```bash
python -m pytest tests/deterministic
```
*Current status: 22 passed.*

### Unit Test Suite
```bash
python -m pytest tests/unit
```
*Current status: 154 passed, 2 skipped (integration-dependent assertions).*

### Full Offline Regression Suite
```bash
python -m pytest
```
*Current status: 177 passed, 2 skipped, 13 deselected.*

### Live Integration Tests
Requires live PostgreSQL running on port 5432 and FastAPI running on port 8000:
```bash
python -m pytest tests/live_integration -m "live_integration"
```
*Current status: 13 passed when services are running.*

## 9. Current Status & Known Limitations

- **Source Discovery**: Web portals frequently update UI patterns; portal crawl trees should be re-verified periodically using `scripts/verify_sources.py`.
- **Live Infrastructure Dependency**: `tests/live_integration` requires an accessible PostgreSQL instance and active API daemon; automated CI environments running offline will deselect them by default via `pytest.ini`.
- **Batch 13 Certification**: Batch 13 verification artifacts remain in progress pending live staging deployment certification.
