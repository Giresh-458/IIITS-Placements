import argparse
import asyncio

from src.config.settings import settings
from src.storage.database import DatabaseManager


def validate_config() -> int:
    budget = settings.crawl_budget
    eligibility = settings.eligibility
    errors = []

    positive_values = {
        "max_runtime_seconds": budget.max_runtime_seconds,
        "max_urls": budget.max_urls,
        "max_pages_per_source": budget.max_pages_per_source,
        "request_timeout_seconds": budget.request_timeout_seconds,
        "browser_timeout_seconds": budget.browser_timeout_seconds,
        "recent_event_days_window": eligibility.recent_event_days_window,
    }
    non_negative_values = {
        "max_depth": budget.max_depth,
        "max_browser_pages": budget.max_browser_pages,
        "max_pdf_pages": budget.max_pdf_pages,
        "max_retries": budget.max_retries,
        "per_domain_delay_seconds": budget.per_domain_delay_seconds,
        "cse_min_lpa": eligibility.cse_min_lpa,
        "ece_min_lpa": eligibility.ece_min_lpa,
    }

    for name, value in positive_values.items():
        if value <= 0:
            errors.append(f"{name} must be greater than zero (received {value!r}).")
    for name, value in non_negative_values.items():
        if value < 0:
            errors.append(f"{name} must not be negative (received {value!r}).")

    if not settings.database_url.strip():
        errors.append("DATABASE_URL must not be empty.")
    if not settings.ollama_endpoint.strip():
        errors.append("OLLAMA_ENDPOINT must not be empty.")

    if errors:
        print("CONFIG_VALIDATION = FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("CONFIG_VALIDATION = PASS")
    print(f"max_runtime_seconds = {budget.max_runtime_seconds}")
    print(f"max_urls = {budget.max_urls}")
    print(f"max_pages_per_source = {budget.max_pages_per_source}")
    print(f"max_depth = {budget.max_depth}")
    print(f"max_browser_pages = {budget.max_browser_pages}")
    print(f"max_pdf_pages = {budget.max_pdf_pages}")
    print(f"max_retries = {budget.max_retries}")
    print(f"recent_event_days_window = {eligibility.recent_event_days_window}")
    return 0


async def check_database_health() -> int:
    """Check the configured database connection; do not imply other services ran."""
    manager = DatabaseManager()
    healthy = False
    failure_type = None
    disconnect_failed = False

    try:
        await manager.connect()
        healthy = await manager.check_health()
    except Exception as exc:
        # Deliberately avoid printing connection strings or full driver errors.
        failure_type = type(exc).__name__
    finally:
        try:
            await manager.disconnect()
        except Exception as exc:
            disconnect_failed = True
            print(f"DATABASE_DISCONNECT = FAIL ({type(exc).__name__})")

    if failure_type:
        print(f"DATABASE_CONNECTIVITY = FAIL ({failure_type})")
        return 1
    if healthy and not disconnect_failed:
        print("DATABASE_CONNECTIVITY = PASS")
        return 0
    if not disconnect_failed:
        print("DATABASE_CONNECTIVITY = FAIL")
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Placement Intelligence repository health and configuration checks"
    )
    parser.add_argument(
        "command",
        choices=["health", "validate-config"],
        help="Check database connectivity or validate configured crawl/eligibility budgets",
    )
    args = parser.parse_args(argv)

    if args.command == "health":
        return asyncio.run(check_database_health())
    return validate_config()


if __name__ == "__main__":
    raise SystemExit(main())
