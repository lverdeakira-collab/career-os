---
name: career-profile
description: Read and explain verified Career_OS candidate evidence without inferring new facts. Use for candidate fact checks, evidence lookup, or distinguishing Candidate Truth from user strategy and employment policy.
---

# Career Profile

1. Read `15_Application_Engine/canonical_sources.json` from the Career_OS root.
2. Load only the registered `candidate_truth` for facts and its evidence links when verification is needed.
3. Load `candidate_strategy` only for preferences; never promote a preference into Candidate Truth.
4. Load employment policy only for policy questions; never write policy values into Candidate Truth.
5. Preserve nulls as unknown. Do not infer skills, proficiency, immigration status, salary preference, or experience.
6. Return evidence paths with factual statements and flag unsupported requests.
