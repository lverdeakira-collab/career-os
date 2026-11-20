# Career_OS Job Discovery Engine v0.1

This module implements three public ATS connector types with the same interface:

- Lever Public API
- Greenhouse Public API
- Ashby Public Job Board API

Each connector provides `discover()`, `fetch_job()`, `extract_source_fields()`, and `normalize_source_metadata()`. Source parsing is isolated from Stage 3 scoring.

## Safety boundary

Connectors access only public JSON endpoints with a transparent Career_OS user agent and a 20-second timeout. They do not authenticate, manage cookies, bypass CAPTCHAs, evade rate limits, imitate users, or submit applications. HTTP/access failures become `SOURCE_ACCESS_LIMITED` and do not terminate other sources.

## Pipeline

`DISCOVERED → RAW_CAPTURED → NORMALIZED → DEDUPLICATED → READY_FOR_EVALUATION`

Raw records retain the source payload, payload SHA-256, full available JD text/HTML, source and application URLs, source IDs, retrieval time, and metadata. The Stage 3 canonical Job Schema is not extended: Stage 4 provenance is stored in a sidecar named `<Job_ID>.provenance.json`.

## Running a controlled discovery

```bash
PYTHONDONTWRITEBYTECODE=1 python3 11_Automation/job_discovery/run_discovery.py \
  --career-os-root /path/to/Career_OS \
  --output-root /path/to/Career_OS \
  --config 11_Automation/job_discovery/discovery_sources.json
```

Review and update the explicit source allowlist before future runs. Do not exceed approved source scope or use Stage 4 to create application materials.
