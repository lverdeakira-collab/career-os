# Knowledge-base layout

Career OS started as a numbered knowledge base that keeps every kind of career material in a predictable place. The engine reads from it; agents write to it only with user-verified facts. Only the engine folders and blank templates are published in this repository.

| Folder | Purpose | Template |
|---|---|---|
| `01_Profile` | Verified personal and career profile | — |
| `02_Experience` | One structured record per role | `templates/experience_template.md` |
| `03_Projects` | One structured record per project | `templates/project_template.md` |
| `04_Skills` | Skills with supporting evidence | `templates/skill_template.md` |
| `05_STAR` | Situation–Task–Action–Result stories | `templates/star_template.md` |
| `06_Resume_Rules` | Resume rules by target role family | — |
| `07_Job_Targets` | Target companies, roles and criteria | `templates/company_template.md` |
| `08_Job_Search` | Discovery runs, raw and normalized jobs, seen-job memory | generated |
| `08_Portfolio` | Portfolio entries and assets | `templates/portfolio_template.md` |
| `09_Prompts` | User-approved prompts by workflow | — |
| `10_Application_Tracker` | Job index, application and outcome trackers | generated |
| `10_Workflows` | Documented operating procedures | — |
| `11_Applications` | Per-application state (drafted → ready for review → submitted) | generated |
| `11_Automation` | **Engine code (published)** | — |
| `12_AI_Memory` | Long-term knowledge approved for AI use | — |
| `13_Interview` | Interview preparation linked to `Application_ID` / `Job_ID` | — |
| `14_Outcomes` | Verified outcomes used to calibrate policy, never to overwrite facts | — |
| `15_Application_Engine` | **Orchestration and rule documents (published)** | — |
| `99_Documentation` | Architecture and conventions | — |

## Rules for every folder

- Add only information supplied or verified by the user.
- Never fabricate achievements, metrics, projects, experience or background details.
- Keep templates blank until real input exists.
- Keep stable identifiers and update indexes when records change.
- Lower-priority sources (generated material, outcomes) never overwrite higher-priority facts automatically.
