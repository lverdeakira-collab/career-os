# Career_OS Duplicate Detection Rules v0.1

Duplicate detection considers, in descending confidence:

1. Exact normalized source URL.
2. Same normalized company, normalized role title, and location.
3. Same company plus highly similar cleaned JD text.
4. Repost indicators such as the same employer/role/location with changed posting dates.

Potential duplicates are never deleted automatically. The engine assigns a stable `Duplicate_Group` and selects one canonical record, normally the earliest valid `Job_ID`. All other records retain their own immutable IDs and point to `Duplicate_Canonical_Job_ID`.

The canonical record may be updated with new factual source information, but duplicates remain preserved for auditability. Duplicate grouping never authorizes a second application; one `Job_ID` still permits zero or one application unless explicitly approved.
