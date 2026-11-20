# Eligibility rules

Career OS does not hard-code any country's immigration, work-pass or labour rules. Instead:

1. **The candidate states their own facts** in `candidate_profile.json`:

   ```json
   "work_authorization_facts": {
     "authorized_countries": ["Country A"],
     "citizen_or_resident_countries": ["Country A"],
     "requires_sponsorship_countries": ["Country B"]
   }
   ```

2. **The candidate chooses how each restriction is handled** in `candidate_strategy.json`:

   ```json
   "eligibility_preferences": {
     "citizen_or_resident_only": "REVIEW",
     "no_sponsorship": "REVIEW",
     "unrestricted_work_rights_required": "REVIEW",
     "local_candidates_preferred": "IGNORE",
     "work_authorization_not_stated": "REVIEW",
     "required_language_missing": "SKIP",
     "required_language_unverified": "REVIEW"
   }
   ```

| Action | Effect on the hard gate |
|---|---|
| `SKIP` | `FAIL` — but only when the candidate's facts confirm the gap; otherwise softened to `MANUAL_REVIEW` |
| `REVIEW` | `MANUAL_REVIEW` |
| `IGNORE` | Signal is recorded, gate unaffected |

A candidate who is already authorized for (or a citizen/resident of) the job's country is never blocked by these restrictions.

## Files

- `preferences.py` — defaults, validation and action → effect mapping
- `work_authorization.py` — detects citizen-only, no-sponsorship, right-to-work and local-preference wording
- `language_classifier.py` — classifies required / preferred / contextual language mentions
- `language_aliases.json` — editable language-name aliases
