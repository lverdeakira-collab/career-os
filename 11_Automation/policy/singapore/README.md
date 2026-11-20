# Singapore Employment Policy Layer

This package is the canonical, versioned Singapore employment-policy source for Career_OS. It is separate from both `candidate_profile.json` (facts) and `candidate_strategy.json` (preferences).

## Canonical files

- `mom_ep_policy.json`: EP qualifying-salary versions, COMPASS semantics, C1 distinction, and the no-quota/no-levy rule.
- `fcf_rules.json`: Fair Consideration Framework advertising requirements and exemptions.
- `language_constraints.json`: job-language classification authority and aliases.
- `employment_policy.schema.json`: shared provenance metadata contract.
- `evaluate_policy.py`, `work_authorization.py`, and `language_classifier.py`: deterministic enforcement.

Each policy record carries authority, URL, effective period, version, and verification date. Policy selection is date-aware. No future-effective or expired rule may silently become active.

## Safety semantics

- Never infer EP eligibility from company size.
- Never treat EP as an S Pass quota system.
- Never equate an unseen MyCareersFuture advertisement with EP ineligibility.
- Keep personal salary preferences independent of MOM thresholds and COMPASS C1 benchmarks.
- Employer-side COMPASS facts are normally unavailable at job-screening time; use `UNKNOWN` or `HUMAN_REVIEW`.
- Update this package when official rules change; do not edit Candidate Truth.
