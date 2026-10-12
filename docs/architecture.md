# Architecture Contract

## System Purpose
A self-hosted system for college placement intelligence and recruiter outreach discovery. The final system discovers hiring opportunities and identifies potential recruiter leads for IIIT Sri City based on hiring activities at other target colleges.

## Component Boundaries
- **API (FastAPI):** Exposes endpoints for managing runs, viewing events, and triggering manual operations.
- **Workflow Orchestration (LangGraph):** Manages the multi-stage pipeline of discovering, crawling, extracting, validating, and persisting data.
- **Database (PostgreSQL):** The definitive source of truth for extracted events, metadata, and telemetry.
- **LLM (Ollama):** Local extraction, classification, and validation processing.
- **Browsing (Playwright/Crawlee):** Fetching and executing JS when required, within strict bounded limits.

## LangGraph Workflow
The system orchestrates a pipeline through agents using a shared `PipelineState`.
1. **Source Registry Agent**
2. **Discovery Agent**
3. **Crawl Agent**
4. **Content Extraction Agent**
5. **Hiring Event Extraction Agent**
6. **Eligibility/Role Agent**
7. **Status/Currentness Agent**
8. **Evidence Validation Agent**
9. **Contact Intelligence Agent**
10. **Phone Verification Agent**
11. **Persistence Agent**
12. **Telemetry Agent**

## Source Hierarchy Concept
A Source represents a specific URL tied to a College. Not all sources have the same access level.
- `PUBLIC_HTML`, `PUBLIC_JS`, `AUTHENTICATED`, etc.

## Trust / Evidence Rules
- **Never Invent Data:** Unknown data remains null.
- **Evidence First:** Every fact must trace back to an `Evidence` record containing source URL, timestamp, and confidence.
- **Source Access ≠ Source Truth:** The existence of a page does not guarantee readable public facts.
- **No LLM Fabrication:** LLMs classify and normalize; they do not invent missing facts (e.g., CTC or recruiters).

## Database Responsibility
PostgreSQL is the source of truth for relations (events, companies, jobs). Large binary objects (PDFs, raw HTML) may eventually be stored on filesystem/object storage, with references in DB.

## Browser / HTTP Escalation Principle
- Use simple HTTP first.
- Only escalate to a headless browser (Playwright) if the source requires JS execution (`PUBLIC_JS`), maintaining a strict concurrency budget.

## Contact Intelligence Separation
Finding an event is separate from finding a contact.
- A missing contact does not invalidate an event.
- Contact role requires verification; a random phone number is not a recruiter by default.

## Future Batch Roadmap
- **Batch 1 (IMPLEMENTED):** Foundation, boundaries, schema interfaces, and stubs.
- **Batch 2 (PLANNED):** Source Registry and Discovery implementation.
- **Batch 3 (PLANNED):** Crawlee integration and HTTP fetching.
- **Batch 4 (PLANNED):** Playwright integration and advanced JS handling.
- **Batch 5 (PLANNED):** Content & Event Extraction (LLM integration).
- **Batch 6 (PLANNED):** Classification and Status engine (15-day window).
- **Batch 7 (PLANNED):** Contact Intelligence & Phone Verification.
- **Batch 8 (PLANNED):** Database Persistence & FastAPI full endpoints.
- **Batch 9 (PLANNED):** UI / Dashboard exports.

**NOTE:** Features labeled PLANNED are NOT YET IMPLEMENTED in Batch 1.
