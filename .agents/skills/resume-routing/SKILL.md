---
name: resume-routing
description: Route a job to one frozen Career_OS Base Resume and optionally a secondary evidence pool. Use for resume selection or cross-functional route review without tailoring, merging, or editing resumes.
---

# Resume Routing

1. Resolve the allowed Base Resumes and router through `15_Application_Engine/canonical_sources.json`.
2. Run `11_Automation/resume_router/route_resume.py` using responsibilities and function before title.
3. Emit exactly one primary resume when evidence supports routing.
4. Emit an optional secondary resume only when the canonical threshold permits it; null is valid.
5. Treat the secondary resume as a future evidence pool only. Do not copy bullets or merge Base Resumes.
6. Return low confidence and human review when routing evidence is insufficient.
7. Never modify files under `07_Generated_Resumes/`.
