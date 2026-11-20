# Workflow data model

This reference gives a portable structure for a private job-search workspace. Adapt field names to the user's existing system rather than duplicating state.

## Source-of-truth order

1. User's explicit current instruction.
2. User-confirmed preference or answer stored with provenance and date.
3. Candidate evidence documents for biographical claims.
4. The original job posting or application form for role requirements.
5. Derived summaries, model interpretations, and generated documents.

When sources conflict, do not silently overwrite the higher-priority source. Flag the conflict and ask only if it affects the current decision.

## Suggested entities

### Candidate profile

Store factual claims with a source reference and, where relevant, a confirmation date. Separate verified facts from preferences and inferred summaries. Keep sensitive identifiers in an access-controlled source, not in general-purpose run logs.

### Role record

Suggested fields: stable role ID, source URL, employer, title, location, date observed, posting date if known, original description reference, deduplication key, screening stage, decision, reason codes, uncertainty notes, and resume/material routing.

Keep the source posting unchanged. Put normalized fields and interpretation in separate fields so later reviewers can trace decisions.

### Application record

Suggested fields: role ID, current state, last updated time, completed fields, unresolved fields, queued questions, attached material references, blocker details, and verified external outcome. Do not store credentials or authentication tokens.

## Example state progression

`DISCOVERED` → `DEDUPLICATED` → `SCREENED` → `REVIEW_REQUIRED` or `QUALIFIED` → `PREPARING` → `READY_FOR_USER_REVIEW` → `USER_SUBMITTED` or another verified terminal outcome.

Use `BLOCKED` for access, authentication, identity checks, or technical failures. Use `WITHDRAWN` or `REJECTED` only when supported by an explicit decision or verified event. Keep the source and reason for every transition.

Never infer `USER_SUBMITTED` from a prepared form, an open confirmation page, or an agent action. Record it only after the user reports submission or a clearly verified external status establishes it.

## Reconciliation

Track counts separately for roles discovered, unique roles after deduplication, roles screened, job pages opened, qualified roles, forms prepared, and outcomes verified. Each count should be reproducible from the per-role ledger. A role stopped at an earlier stage should retain its stage and reason so totals can be audited.

## Privacy review before sharing

Before exporting or publishing workflow material, inspect content and metadata for direct identifiers, distinctive biography, employer/job-specific application trails, private URLs, local filesystem paths, timestamps tied to a person, hidden document properties, embedded images, and secrets. Replace examples with synthetic values and rerun the review after edits. Do not publish raw trackers, profile stores, logs, or generated candidate documents.
