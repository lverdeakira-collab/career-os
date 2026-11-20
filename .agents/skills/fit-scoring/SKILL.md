---
name: fit-scoring
description: Calculate and explain a deterministic Career_OS job Fit Score after gap and hard-gate evaluation. Use for score audits, decision-band checks, or evidence-based job ranking.
---

# Fit Scoring

1. Resolve the scoring config and engine through `15_Application_Engine/canonical_sources.json`.
2. Require a completed Gap Matrix and circuit-breaker result before scoring.
3. Run `11_Automation/fit_scoring/score_job.py`; never assign or alter the final numeric score manually.
4. Verify that the six components sum to the canonical total.
5. Apply the canonical gate and circuit-breaker overrides before the score band.
6. Keep assessment confidence separate from Fit Score.
7. Explain the stored breakdown and decision without inventing evidence.
