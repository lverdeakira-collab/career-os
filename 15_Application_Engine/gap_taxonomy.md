# Gap Taxonomy

Each requirement in a posting is classified against the Candidate Profile. Credit values are set in `11_Automation/fit_scoring/weights.json` → `evidence_values`.

| Category | Meaning | Default credit | Gate effect |
|---|---|---:|---|
| `MATCHED` | The profile lists the skill (exact name, alias, or named inside the requirement) or the responsibility tag | 1.00 | none |
| `PARTIAL` (related) | Most of the requirement's words appear in one verified skill | 0.75 | none |
| `PARTIAL` (other) | Partial evidence | 0.65 | none |
| `PARTIAL` (transferable) | An adjacent, transferable evidence tag | 0.55 | none |
| `UNKNOWN` | Not evidenced either way | 0.25 | manual review only for types listed in `hard_filters/rules.json` → `manual_review_for_unverified` (default: `MUST_HAVE`, `LICENSE`) |
| `MISSING` | The profile confirms the candidate does not have it | 0.00 | a critical `MISSING` requirement forces `SKIP` |
| `NOT_APPLICABLE` | Not relevant to the decision | excluded | none |

Unknown is deliberately different from missing: a posting can mention a skill the profile simply has not recorded yet, which should lower the score without being treated as a confirmed gap.

Each gap records the requirement, requirement type (`MUST_HAVE`, `REQUIRED`, `PREFERRED`, `RESPONSIBILITY`, `LANGUAGE`, `LICENSE`, `WORK_AUTHORIZATION`), category, evidence and source field.

Missing requirements remain gaps. The engine never inserts a missing skill or experience into the Candidate Profile, base resume or derived material.
