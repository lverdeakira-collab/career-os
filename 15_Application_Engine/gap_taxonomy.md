# Career_OS Gap Taxonomy v0.1

| Category | Meaning | Scoring treatment |
|---|---|---|
| `VERIFIED_MATCH` | Direct verified Career_OS evidence exists | Full credit |
| `PARTIAL_MATCH` | Evidence covers part, not all, of the requirement | Partial credit |
| `TRANSFERABLE` | Adjacent verified evidence is relevant but not identical | Partial credit |
| `MISSING` | Explicit requirement with no verified evidence | Zero; hard gate only if mandatory |
| `UNKNOWN` | Requirement or evidence is too ambiguous | Zero and potentially manual review |

Each gap records the requirement, requirement type (`MUST_HAVE`, `REQUIRED`, `PREFERRED`, `NICE_TO_HAVE`, or `RESPONSIBILITY`), category, and evidence reference.

Missing requirements remain gaps. The engine must never insert a missing skill or experience into the Candidate Profile, Base Resume, or derived material.
