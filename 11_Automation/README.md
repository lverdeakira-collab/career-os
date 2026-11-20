# Career_OS Automation

Stage 3 modules implement job normalization, Hard Gates, gap analysis, Fit Score, resume routing, duplicate record checks, and schema validation. Stage 3 Hardening v1.0 adds versioned Singapore policy, explicit work-authorization/language semantics, confirmed-missing circuit breakers, untrusted-JD detection, and additive compatibility fields.

Stage 4 adds a separate `job_discovery/` package for approved public ATS discovery, raw capture, source normalization, vacancy-level deduplication, Seen Job memory, and run logging. Discovery does not change the Candidate Profile or decide fit independently; it passes canonical jobs into the existing Stage 3 engine.

No module fills forms, logs into job portals, tailors resumes, contacts recruiters, or submits applications.

Canonical sources are registered in `../15_Application_Engine/canonical_sources.json`. Portable `.agents/skills/` instructions point to these files and do not duplicate truth or rules.
