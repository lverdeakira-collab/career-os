---
name: singapore-eligibility
description: Assess Singapore work-authorization, Employment Pass, COMPASS, FCF, salary, and language evidence using versioned Career_OS policy. Use for Singapore job eligibility analysis where policy or posting language is relevant.
---

# Singapore Eligibility

1. Resolve the policy package through `15_Application_Engine/canonical_sources.json`.
2. Read policy metadata and select the active record for the assessment date. Do not apply future or expired values.
3. Use the deterministic evaluators in `11_Automation/policy/singapore/`.
4. Keep advertised salary, personal salary preference, EP qualifying salary, and COMPASS C1 benchmark separate.
5. Do not infer EP eligibility from company size or from the absence of a visible MyCareersFuture listing.
6. Do not treat preferred local/language wording as an automatic disqualifier.
7. Emit uncertainty and request human review when age, sector, employer COMPASS data, or authorization status is unavailable.
