# Application Engine

Orchestration layer of Career OS. It wires the modules in `../11_Automation/` into one evaluation run and holds the human-readable rule documents.

## Contents

| File | Purpose |
|---|---|
| `run_dry_run.py` | Evaluates one job object or an array of jobs: normalization → hard gates → gap analysis → fit score → resume routing |
| `candidate_profile.json` | **Synthetic** Candidate Truth used for tests and demos |
| `candidate_strategy.json` | **Synthetic** preferences, including `eligibility_preferences` (how posting restrictions are treated) |
| `canonical_sources.json` | Registry pointing to every canonical rule, schema and config file |
| `job_schema.json`, `application_schema.json` | Entry points to the JSON Schemas in `../11_Automation/schemas/` |
| `hard_gate_rules.md` | Eligibility rules applied before scoring |
| `fit_scoring_model.md` | The transparent 100-point model |
| `gap_taxonomy.md` | Evidence-gap classifications |
| `resume_routing_rules.md` | Deterministic two-base routing policy |
| `career_taxonomy.md` | Three functional routes |
| `status_machine.md` | Job and application states |
| `factual_integrity_rules.md`, `application_policy.md`, `duplicate_detection_rules.md` | Integrity and process rules |
| `test_jobs/`, `stage4_test_fixtures/` | Synthetic jobs and edge cases |

## Source-of-truth hierarchy

1. Verified experience, projects, education and skills
2. Candidate Profile
3. Frozen base resumes
4. Job-specific derived materials
5. Application, interview and outcome records

Lower tiers never overwrite higher-tier facts automatically.

## Dry run

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 15_Application_Engine/run_dry_run.py \
  --input 15_Application_Engine/test_jobs/synthetic_test_jobs.json \
  --output /tmp/manual_run.json \
  [--profile path/to/your/private/candidate_profile.json] \
  [--strategy path/to/your/private/candidate_strategy.json]
```

## Boundary

The engine scores and routes. It does not generate application materials, fill forms or submit applications.
