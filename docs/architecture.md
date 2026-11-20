# Architecture

## Separation of concerns

| Layer | Lives in | Changed by |
|---|---|---|
| Candidate Truth — verified facts only | `candidate_profile.json` (private in real use) | the user, with evidence |
| Candidate Strategy — preferences and boundaries | `candidate_strategy.json` (private in real use) | the user |
| Employment policy — public, versioned, dated | `11_Automation/policy/singapore/` | policy updates with source URL and verification date |
| Rules and weights | `hard_filters/rules.json`, `fit_scoring/weights.json`, `resume_router/routing_rules.json` | deliberate, reviewed diffs |
| Enforcement | Python modules | code changes covered by validation suites |
| Semantic interpretation | LLM, inside agent skills | bounded: classify evidence only |

`15_Application_Engine/canonical_sources.json` is the registry that points to each of these. Skills and documentation reference the registry instead of copying values, so there is exactly one place to change any rule.

## Evaluation order

1. **Normalize** the posting into the canonical job schema; keep the raw text and provenance.
2. **Detect untrusted instructions** inside the job description and flag them.
3. **Classify policy signals**: work-authorization wording (citizens/PR only, no sponsorship, local preference), language requirements (required vs preferred), EP salary feasibility for the posting date.
4. **Hard gates**: seniority, location and employment type, experience requirement semantics, mandatory education or licences, policy results → `PASS`, `MANUAL_REVIEW` or `FAIL`.
5. **Gap analysis**: each requirement becomes `DIRECT_MATCH`, `PARTIAL_MATCH`, `UNKNOWN` or `MISSING`. Only *confirmed* missing critical requirements trip the circuit breaker; unknowns go to review.
6. **Fit score**: six fixed components summing to 100, mapped to a decision band, then overridden by gate results.
7. **Resume routing**: choose one of two frozen base resumes using deterministic rules over three functional routes.
8. **Human checkpoint**: results are written as records; submission is always a user action.

## Status machine

Jobs: `DISCOVERED → NORMALIZED → HARD_GATE_FAILED | SCORED | READY_FOR_REVIEW → SHORTLISTED | SKIPPED`.

Applications: `NOT_APPLIED → APPROVED_FOR_APPLICATION → MATERIALS_GENERATED → READY_TO_SUBMIT → SUBMITTED → RECRUITER_SCREEN → INTERVIEW → FINAL_INTERVIEW → OFFER | REJECTED | WITHDRAWN | CLOSED`.

`SUBMITTED` is recorded only after the user confirms submission or a verified external status shows it.
