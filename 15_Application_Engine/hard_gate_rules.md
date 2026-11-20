# Career_OS Hard Gate Rules v0.1

Hard gates run before the Fit Score and return `PASS`, `MANUAL_REVIEW`, or `FAIL`.

## Gate categories

1. Location compatibility
2. Seniority compatibility
3. Mandatory years of experience
4. Mandatory language
5. Work authorization or sponsorship
6. Mandatory technical qualification
7. Mandatory professional license
8. Fundamentally incompatible profession
9. Role type outside Career_OS scope

Ambiguous information produces `MANUAL_REVIEW`, not `FAIL`. Preferred or desirable qualifications are never converted into hard gates.

## Experience-year policy

- 0–1 years: compatible.
- 1–2 years: generally compatible.
- More than 2 through 3 years: review unless graduate/equivalent wording or strong evidence resolves eligibility.
- More than 3 but under 5 years: generally weak; use manual review unless the mandatory mismatch is explicit.
- 5+ years: fail for normal early-career applications.

This is a Career_OS decision rule, not a candidate fact.

## Mandatory-language policy

English and Chinese are verified as listed languages; proficiency levels are unknown. A clear mandatory unsupported language fails. An ambiguous language or proficiency requirement requires manual review.

## Mandatory technical/license policy

A missing capability fails only when the JD establishes it as mandatory. Context controls classification; the words “required” or “preferred” are signals, not sufficient evidence by themselves.

## Precedence

- `FAIL` → `SKIP / HARD_GATE_FAILED`, regardless of score.
- `MANUAL_REVIEW` → `REVIEW`, regardless of score.
- `PASS` → the score band determines the decision.
