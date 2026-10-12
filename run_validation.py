import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.models.domain import HiringEventCandidate
from src.telemetry.crawl_metrics import CrawlTelemetry


ARTIFACT_DIR = Path("artifacts")
REQUIRED_ARTIFACTS = (
    "crawl_seed_registry.json",
    "discovered_events.json",
    "crawl_telemetry.json",
)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as artifact_file:
        return json.load(artifact_file)


def run_validation() -> int:
    """Validate available crawl artifacts and report recorded telemetry.

    This checks artifact presence and schema only. It does not claim that a
    crawler process exited successfully or that browser fixtures were executed;
    those facts must come from actual process results and test output.
    """
    errors = []
    payloads = {}

    for name in REQUIRED_ARTIFACTS:
        path = ARTIFACT_DIR / name
        if not path.is_file():
            errors.append(f"Missing required artifact: {path}")
            continue
        try:
            payloads[name] = _load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Cannot read {path}: {type(exc).__name__}: {exc}")

    if errors:
        print("ARTIFACT_VALIDATION = FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    registry = payloads["crawl_seed_registry.json"]
    if not isinstance(registry, list):
        errors.append("crawl_seed_registry.json must contain a JSON list.")
    else:
        for index, source in enumerate(registry):
            if not isinstance(source, dict):
                errors.append(f"Source registry record {index} must be a JSON object.")
                continue
            for field in ("institution", "seed_url", "source_category"):
                if not isinstance(source.get(field), str) or not source[field].strip():
                    errors.append(
                        f"Source registry record {index} requires a non-empty {field!r}."
                    )

    raw_events = payloads["discovered_events.json"]
    events = []
    if not isinstance(raw_events, list):
        errors.append("discovered_events.json must contain a JSON list.")
    else:
        for index, event in enumerate(raw_events):
            try:
                events.append(HiringEventCandidate.model_validate(event))
            except (ValidationError, TypeError, ValueError) as exc:
                errors.append(
                    f"Discovered event record {index} failed schema validation: {exc}"
                )

    raw_telemetry = payloads["crawl_telemetry.json"]
    telemetry = None
    if not isinstance(raw_telemetry, dict):
        errors.append("crawl_telemetry.json must contain a JSON object.")
    else:
        try:
            telemetry = CrawlTelemetry.model_validate(raw_telemetry)
        except (ValidationError, TypeError, ValueError) as exc:
            errors.append(f"crawl_telemetry.json failed schema validation: {exc}")

    if errors:
        print("ARTIFACT_VALIDATION = FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    source_counts = Counter(event.institution for event in events)
    recent_counts = Counter(event.institution for event in events if event.is_recent)

    print("ARTIFACT_SCHEMA_VALIDATION = PASS")
    print(f"source_registry_records = {len(registry)}")
    print(f"discovered_event_records = {len(events)}")
    print(f"crawl_run_id = {telemetry.run_id}")
    print(f"crawl_duration_seconds = {telemetry.duration_seconds}")
    print(f"crawl_stop_reason_recorded = {telemetry.stop_reason}")
    print(f"sources_attempted = {telemetry.sources_attempted}")
    print(f"sources_succeeded = {telemetry.sources_succeeded}")
    print(f"sources_failed = {telemetry.sources_failed}")
    print(f"pages_attempted = {telemetry.pages_attempted}")
    print(f"pages_succeeded = {telemetry.pages_succeeded}")
    print(f"pages_failed = {telemetry.pages_failed}")
    print(f"http_requests = {telemetry.http_requests}")
    print(f"browser_pages = {telemetry.browser_pages}")
    print(f"browser_escalations = {telemetry.browser_escalations}")
    print(f"browser_failures = {telemetry.browser_failures}")
    print(f"pdfs_processed = {telemetry.pdfs_processed}")
    print(f"crawler_exceptions_recorded = {len(telemetry.exceptions)}")

    print("\nEVENT_COUNTS_BY_INSTITUTION")
    print(f"{'Institution':<40} | {'Events':>6} | {'Recent':>6}")
    print("-" * 59)
    for institution in sorted(set(source_counts) | set(recent_counts)):
        print(
            f"{institution:<40} | {source_counts[institution]:>6} | "
            f"{recent_counts[institution]:>6}"
        )

    if telemetry.exceptions:
        print(
            "\nNOTE: Crawl telemetry records exceptions. Schema validation does not "
            "mean the crawl itself was error-free."
        )
    print(
        "\nThis report validates the artifacts currently on disk; it does not "
        "prove crawler process exit status or browser-fixture execution."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run_validation())
