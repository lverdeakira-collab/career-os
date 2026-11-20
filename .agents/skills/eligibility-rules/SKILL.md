---
name: eligibility-rules
description: Assess work-authorization, sponsorship and language restrictions in a posting against the candidate's own facts and chosen eligibility preferences. Use when a posting mentions citizenship, residency, sponsorship, right to work or required languages.
---

# Eligibility Rules

1. Resolve the eligibility package through `15_Application_Engine/canonical_sources.json`.
2. Read the candidate's facts from `work_authorization_facts` (authorized countries, citizenship/residency countries, countries needing sponsorship) and languages from the Candidate Profile. Never infer them.
3. Read the candidate's choices from `candidate_strategy.json` → `eligibility_preferences`. Each restriction maps to `SKIP`, `REVIEW` or `IGNORE`; missing keys use the defaults in `11_Automation/eligibility/preferences.py`.
4. Use the deterministic evaluators in `11_Automation/eligibility/`; do not assign the hard-gate effect yourself.
5. `SKIP` applies only when the candidate's facts confirm the gap. If the candidate's status for the job country is unknown, the result is `REVIEW`.
6. Treat "preferred" wording as a preference, never as a requirement.
7. The engine encodes no country's immigration or labour rules. If the user wants a jurisdiction-specific rule, they express it through their own facts and preferences.
