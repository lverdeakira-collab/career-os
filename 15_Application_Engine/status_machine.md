# Career_OS Status Machine v0.1

Only controlled status values are valid.

## Job statuses

`DISCOVERED` → `NORMALIZED` → one of:

- `HARD_GATE_FAILED` → `SKIPPED`
- `SCORED` → `SHORTLISTED`
- `SCORED` → `SKIPPED`
- `SCORED` → `READY_FOR_REVIEW`

`READY_FOR_REVIEW` may become `SHORTLISTED` or `SKIPPED` after user review. No application is implied by a job status.

## Application statuses

`NOT_APPLIED` → `APPROVED_FOR_APPLICATION` → `MATERIALS_GENERATED` → `READY_TO_SUBMIT` → `SUBMITTED`

After submission, allowed progress states are `RECRUITER_SCREEN`, `INTERVIEW`, `FINAL_INTERVIEW`, `OFFER`, `REJECTED`, `WITHDRAWN`, and `CLOSED`. `WITHDRAWN`, `REJECTED`, and `CLOSED` are terminal; `OFFER` may transition to `CLOSED` after the final outcome is recorded.

An application record requires explicit user consent. Creating a real `Application_ID` before approval/submission is prohibited.

Machine-readable values and transitions are in `../11_Automation/schemas/status_definitions.json`.
