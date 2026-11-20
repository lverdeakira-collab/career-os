# Career OS

**A privacy-first, rule-driven job-search engine for early-career candidates in Singapore.**

Career OS turns a job search into an auditable pipeline: discover roles from public applicant-tracking systems, normalize them into one schema, apply explicit eligibility gates (including Singapore work-pass policy), score fit with a transparent 100-point model, route each role to the right base resume, and stop at a human checkpoint before anything is submitted.

The core design principle: **JSON/CSV records are truth, deterministic Python enforces rules, and a language model only handles bounded semantic judgments.** An LLM may classify evidence; it may not assign weights, compute the final score, change decision bands, or bypass overrides.

> This repository contains the engine, schemas, rules and agent skills only. All candidate data in it is **synthetic**. See [PRIVACY.md](PRIVACY.md).

---

## What it does

```
Public ATS boards ──► Discovery ──► Normalization ──► Hard gates ──► Gap analysis ──► Fit score ──► Resume routing ──► Human review
 (Greenhouse,          raw capture,   canonical job     seniority,     MISSING vs        6-component    2 frozen base       nothing is
  Lever, Ashby)        dedup, seen-   schema, title     location,      UNKNOWN,          100-pt model,  resumes, deter-     submitted
                       job memory     aliases           work pass,     circuit breaker   decision band  ministic rules      automatically
                                                        language
```

| Stage | Module | Highlights |
|---|---|---|
| Discovery | `11_Automation/job_discovery/` | Connectors for Greenhouse, Lever and Ashby public boards; raw capture with provenance; vacancy-level deduplication; "seen job" memory so roles are never re-processed |
| Normalization | `11_Automation/job_normalization/` | Maps every posting to one canonical job schema; title-alias table |
| Hard gates | `11_Automation/hard_filters/` | Seniority, location/employment type, experience-requirement semantics, mandatory education/licences |
| Singapore policy | `11_Automation/policy/singapore/` | Versioned MOM Employment Pass qualifying-salary tables, Fair Consideration Framework rules, work-authorization and language-requirement classifiers. Policy is selected by date (`--policy-as-of`) for reproducibility |
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
│   ├── policy/singapore/       # versioned MOM EP / FCF / language rules
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

Each result contains the hard-gate status and reasons, the gap matrix, the score breakdown, the decision band, the routed base resume, and the Singapore policy interpretation.

To use it for a real search, copy `15_Application_Engine/candidate_profile.json` and `candidate_strategy.json` into a **private** location, fill them with your own verified facts, and pass them with `--profile` / `--strategy`. Never commit them.

---

## Agent skills

- **`.agents/skills/`** — six stage-specific skills (career profile, job evaluation, Singapore eligibility, gap analysis, fit scoring, resume routing). They are deliberately thin: they point to `15_Application_Engine/canonical_sources.json` instead of duplicating facts, weights or policy values.
- **`skills/career-application-ops/`** — a portable workflow skill for running a whole search: run boundaries, staged screening, tailored materials, form preparation with a mandatory human checkpoint, and reconciled tracking.

---

## Status

Discovery, normalization, gating, scoring and routing are implemented and tested. Application-type detection, automated tailoring and form completion are intentionally out of scope for this engine; those steps stay human-reviewed.

Singapore policy tables reflect sources verified in 2026 and must be re-checked against the [Ministry of Manpower](https://www.mom.gov.sg/passes-and-permits/employment-pass/eligibility) before relying on them.

## License

[MIT](LICENSE)
