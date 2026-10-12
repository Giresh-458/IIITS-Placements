# Data Contract

This document outlines the core data models used throughout the pipeline.

## Core Models (IMPLEMENTED in Batch 1)

### `College`
- `id`: unique identifier
- `name`: name of the institution
- `institution_type`: Type of institution (IIT, NIT, IIIT, etc.)
- `domain`: web domain
- `is_target_profile`: Boolean flag indicating if this is the target profile (e.g., IIIT Sri City).

### `Source` and `SourceProfile`
- Defines the URL, college mapping, priority, and `access_status` (`PUBLIC_HTML`, `AUTHENTICATED`, etc.).

### `HiringEvent`
- `campus_type`: Enum (`ON_CAMPUS`, `POOL_CAMPUS`, etc.)
- `event_status`: Enum (`UPCOMING`, `ONGOING`, `COMPLETED_RECENT`, etc.)
- References `jobs` and `evidence_ids`.
- Nullable dates for exact schedules if unavailable.

### `Job`
- `ctc_lpa`: Float (Nullable)
- `role_categories`: List of `RoleCategory`
- `eligible_branches`: List
- `cgpa_threshold`: Float (Nullable)

### `Contact` & `PhoneCandidate`
- `role`: Enum (`DIRECT_HR`, `CAMPUS_RECRUITMENT`, etc.)
- `PhoneCandidate`: Stores raw and normalized phone, and `is_verified` flag.

### `Evidence`
- `source_url`: Origin URL
- `source_type`: `SourceAccessClassification`
- `confidence`: Float
- Tracks traceability for extracted facts.

## Enums (IMPLEMENTED in Batch 1)
- `CampusEventType`
- `EventStatus`
- `RoleCategory` (Extensive taxonomy for engineering/software)
- `ContactRole`
- `SourceAccessClassification`
- `SourceIntendedRole`
- `InstitutionType`
