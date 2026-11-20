---
name: gap-analysis
description: Classify Career_OS job requirements against verified Candidate Truth. Use when mapping evidence, distinguishing confirmed missing requirements from unknowns, or auditing critical requirement circuit-breaker decisions.
---

# Gap Analysis

1. Resolve Candidate Truth and gap semantics through `15_Application_Engine/canonical_sources.json`.
2. Use `11_Automation/gap_analysis/classify_gaps.py`; do not reproduce classification rules in prose.
3. Treat `MISSING` as confirmed absence only. Treat insufficient evidence as `UNKNOWN`.
4. Do not create a gap for a requirement absent from the JD.
5. Run `11_Automation/gap_analysis/circuit_breaker.py` only after the Gap Matrix.
6. Trigger only when the canonical record is both `CRITICAL` and `MISSING`; retain evidence, source, and reason.
7. Never resolve a gap by modifying Candidate Truth or a Base Resume.
