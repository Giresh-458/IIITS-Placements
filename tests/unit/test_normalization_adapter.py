from datetime import datetime

from src.models.domain import HiringEventCandidate
from src.orchestration.normalization_adapter import normalize_candidates


def _candidate(event_url, seed_url, evidence_text, discovered_at=None):
    return HiringEventCandidate(
        institution="Trident Academy of Technology",
        company_name="Berger Paints",
        event_title="Campus Drive",
        event_url=event_url,
        source_seed_url=seed_url,
        event_date_raw="16th October 2026",
        campus_mode="VIRTUAL",
        raw_text_excerpt=(
            "Virtual Campus Drive scheduled on 16th October 2026. "
            "Student phone number: 9876543210"
        ),
        evidence={
            "company": {
                "text": evidence_text,
                "method": "structural_regex",
            },
        },
        discovered_at=discovered_at or datetime(2026, 10, 13, 9, 0, 0),
    )


def test_normalization_preserves_source_urls_seed_url_and_field_evidence():
    detail_url = "https://trident.example/placementnotice/berger-paints-drive"
    seed_url = "https://trident.example/placementnotice/"
    candidate = _candidate(
        detail_url,
        seed_url,
        "Berger Paints – GD Schedule",
    )

    normalized = normalize_candidates([candidate])

    assert len(normalized) == 1
    event = normalized[0]
    assert event.event_url == detail_url
    assert event.source_seed_url == seed_url
    assert event.source_urls == [detail_url, seed_url]
    assert len(event.evidence) == 1
    assert event.evidence[0]["field"] == "company"
    assert event.evidence[0]["raw_value"] == "Berger Paints"
    assert event.evidence[0]["evidence_url"] == detail_url
    assert event.evidence[0]["evidence_text"] == "Berger Paints – GD Schedule"
    assert event.evidence[0]["extraction_method"] == "structural_regex"

    # Preserve field-level evidence but do not copy the entire captured text,
    # which may include unrelated student roster/contact data.
    assert event.raw_event_text is None
    assert "9876543210" not in str(event.model_dump())


def test_deduplication_unions_provenance_and_evidence_from_all_candidates():
    detail_url_1 = "https://trident.example/notices/berger-paints-drive"
    seed_url_1 = "https://trident.example/notices/"
    detail_url_2 = "https://trident.example/placementnotice/berger-paints-drive"
    seed_url_2 = "https://trident.example/placementnotice/"

    candidates = [
        _candidate(detail_url_1, seed_url_1, "Berger Paints – GD Schedule"),
        _candidate(
            detail_url_2,
            seed_url_2,
            "Company: Berger Paints",
            datetime(2026, 10, 13, 9, 1, 0),
        ),
    ]

    normalized = normalize_candidates(candidates)

    assert len(normalized) == 1
    event = normalized[0]
    assert event.source_urls == [
        detail_url_1,
        seed_url_1,
        detail_url_2,
        seed_url_2,
    ]
    assert event.source_seed_url == seed_url_1
    assert len(event.evidence) == 2
    assert {item["evidence_text"] for item in event.evidence} == {
        "Berger Paints – GD Schedule",
        "Company: Berger Paints",
    }
