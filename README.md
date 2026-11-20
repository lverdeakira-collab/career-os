# Career OS

**A privacy-first, rule-driven job-search engine for early-career candidates — configurable for any country.**

Career OS turns a job search into an auditable pipeline: discover roles from public applicant-tracking systems, normalize them into one schema, apply eligibility gates that the candidate configures for their own situation, score fit with a transparent 100-point model, route each role to the right base resume, and stop at a human checkpoint before anything is submitted.

The core design principle: **JSON/CSV records are truth, deterministic Python enforces rules, and a language model only handles bounded semantic judgments.** An LLM may classify evidence; it may not assign weights, compute the final score, change decision bands, or bypass overrides.

> This repository contains the engine, schemas, rules and agent skills only. All candidate data in it is **synthetic**. See [PRIVACY.md](PRIVACY.md).

---

## What it does

```
Public ATS boards ──► Discovery ──► Normalization ──► Hard gates ──► Gap analysis ──► Fit score ──► Resume routing ──► Human review
 (Greenhouse,          raw capture,   canonical job     seniority,     MISSING vs        6-component    2 frozen base       nothing is
  Lever, Ashby)        dedup, seen-   schema, title     location,      UNKNOWN,          100-pt model,  resumes, deter-     submitted
                       job memory     aliases           user-chosen    circuit breaker   decision band  ministic rules      automatically
                                                        eligibility
```

| Stage | Module | Highlights |
|---|---|---|
| Discovery | `11_Automation/job_discovery/` | Connectors for Greenhouse, Lever and Ashby public boards; raw capture with provenance; vacancy-level deduplication; "seen job" memory so roles are never re-processed |
| Normalization | `11_Automation/job_normalization/` | Maps every posting to one canonical job schema; title-alias table |
| Hard gates | `11_Automation/hard_filters/` | Seniority, location/employment type, experience-requirement semantics, mandatory education/licences |
| Eligibility rules | `11_Automation/eligibility/` | Detects citizen/resident-only, no-sponsorship, right-to-work and language requirements in a posting. **No country's rules are hard-coded**: the candidate states their own facts and chooses `SKIP` / `REVIEW` / `IGNORE` for each restriction |
| Gap analysis | `11_Automation/gap_analysis/` | Distinguishes *confirmed missing* from *unknown*; a critical-requirement circuit breaker forces SKIP only on confirmed gaps |
| Fit scoring | `11_Automation/fit_scoring/` | Role/function 30 · experience 25 · skills 20 · industry 10 · education 10 · practical fit 5 → `PRIORITY_APPLY` / `APPLY` / `REVIEW` / `SKIP` |
| Resume routing | `11_Automation/resume_router/`, `routing/` | Deterministic choice between two frozen base resumes across three functional routes; vacancy verification |
| QA | `11_Automation/qa/` | JSON-schema validation, duplicate detection, and **untrusted-input detection** — job descriptions are treated as untrusted data and cannot change rules or trigger actions |

### Safety boundaries

- No module logs in to portals, fills forms, contacts recruiters, or submits applications.
- Eligibility always wins over score: a hard-gate `FAIL` forces `SKIP`; `MANUAL_REVIEW` forces `REVIEW`.
- Candidate facts are never inferred or upgraded. A requirement the evidence does not support stays a gap.
- Every decision keeps its reason codes and source, so the pipeline can be audited end to end.

---

## Repository layout

```
.
├── 11_Automation/              # Python engine (stdlib only)
│   ├── job_discovery/          # ATS connectors, dedup, seen-job memory, run logging
│   ├── job_normalization/      # canonical job schema mapping
│   ├── hard_filters/           # eligibility gates
│   ├── eligibility/            # user-configurable work-authorization & language rules
│   ├── gap_analysis/           # gap classification + circuit breaker
│   ├── fit_scoring/            # 100-point model and weights
│   ├── resume_router/ routing/ # base-resume routing and vacancy checks
│   ├── qa/                     # schema validation, duplicates, untrusted input
│   ├── schemas/                # JSON Schemas for every record type
│   └── validation/             # runnable test suites
├── 15_Application_Engine/      # orchestration, rule docs, synthetic profile & test jobs
├── .agents/skills/             # thin-pointer agent skills (Codex-style) for each stage
├── skills/career-application-ops/  # portable, tool-agnostic workflow skill
├── templates/                  # blank knowledge-base templates (experience, project, STAR…)
└── docs/                       # architecture and knowledge-base layout
```

The numbered folder names come from the wider Career OS knowledge base (profile, experience, projects, STAR stories, applications, outcomes…). Only the engine folders and blank templates are published; see [docs/knowledge-base-layout.md](docs/knowledge-base-layout.md).

---

## Quick start

Requires Python 3.10+. No third-party packages.

```bash
# Score the bundled synthetic jobs against the synthetic candidate profile
python3 15_Application_Engine/run_dry_run.py \
  --input 15_Application_Engine/test_jobs/synthetic_test_jobs.json \
  --output /tmp/career_os_dry_run.json

# Run the test suites
./scripts/run_tests.sh
```

Each result contains the hard-gate status and reasons, the eligibility assessment, the gap matrix, the score breakdown, the decision band and the routed base resume.

To use it for a real search, copy `15_Application_Engine/candidate_profile.json` and `candidate_strategy.json` into a **private** location, fill them with your own verified facts, and pass them with `--profile` / `--strategy`. Never commit them.

### Configure eligibility for your situation

Career OS does not assume any country, visa type or government rule. Set your own facts in the profile:

```json
"work_authorization_facts": {
  "authorized_countries": ["Country A"],
  "citizen_or_resident_countries": ["Country A"],
  "requires_sponsorship_countries": ["Country B"]
}
```

…and choose how each kind of posting restriction should be treated in the strategy:

```json
"eligibility_preferences": {
  "citizen_or_resident_only": "REVIEW",
  "no_sponsorship": "SKIP",
  "unrestricted_work_rights_required": "REVIEW",
  "local_candidates_preferred": "IGNORE",
  "work_authorization_not_stated": "REVIEW",
  "required_language_missing": "SKIP",
  "required_language_unverified": "REVIEW"
}
```

`SKIP` fails the hard gate only when your own facts confirm the gap; if your status for that country is unknown it becomes `REVIEW`. Target locations, employment types and an optional personal `salary_floor` are set in the same file. See [11_Automation/eligibility/README.md](11_Automation/eligibility/README.md).

---

## Agent skills

- **`.agents/skills/`** — six stage-specific skills (career profile, job evaluation, eligibility rules, gap analysis, fit scoring, resume routing). They are deliberately thin: they point to `15_Application_Engine/canonical_sources.json` instead of duplicating facts, weights or policy values.
- **`skills/career-application-ops/`** — a portable workflow skill for running a whole search: run boundaries, staged screening, tailored materials, form preparation with a mandatory human checkpoint, and reconciled tracking.

---

## Status

Discovery, normalization, gating, scoring and routing are implemented and tested. Application-type detection, automated tailoring and form completion are intentionally out of scope for this engine; those steps stay human-reviewed.

## License

[MIT](LICENSE)
