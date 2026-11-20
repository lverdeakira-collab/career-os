# Career_OS Fit Scoring Model v0.1

The score is transparent, evidence-based, and totals exactly 100 points.

| Component | Points | Basis |
|---|---:|---|
| Role / Functional Match | 30 | Function, role family, direction, seniority, responsibilities |
| Experience Evidence | 25 | Direct and transferable verified evidence for responsibilities |
| Skills Match | 20 | Required and preferred skills, tools, and domain capabilities |
| Industry Match | 10 | Verified exposure; cross-industry moves are not over-penalized for entry roles |
| Education Match | 10 | Degree level, finance/business alignment, quantitative coursework |
| Career Preference / Practical Fit | 5 | Known location, work arrangement, level, and target direction only |

Required skills control 70% of the Skills component; preferred skills control 30%. When no preferred skills are listed, that portion is neutral rather than punitive. Unsupported claims score zero.

## Bands and hard-gate precedence

- 85–100: `PRIORITY_APPLY`
- 75–84: `APPLY`
- 65–74: `REVIEW`
- 0–64: `SKIP`

Hard Gate `FAIL` always forces `SKIP`. `MANUAL_REVIEW` always forces `REVIEW`. A score cannot override eligibility.

## Confidence

- `HIGH`: core JD fields provide sufficient evidence for classification.
- `MEDIUM`: some important fields are absent or incomplete.
- `LOW`: role requirements, location, seniority, or JD detail are materially insufficient.

Confidence is separate from Fit Score and must not be inflated through inference.

Every result emits the six-component breakdown, top matches, gaps, hard-gate result, decision, and plain-language rationale.
