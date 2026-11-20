"""Load the candidate's eligibility preferences.

Each preference maps a kind of posting restriction to an action:

- ``SKIP``   - treat the restriction as a hard-gate failure.
- ``REVIEW`` - send the job to manual review.
- ``IGNORE`` - record the signal but do not let it affect the gate.

Preferences live in ``candidate_strategy.json`` under
``eligibility_preferences``. Any key the user leaves out falls back to
``DEFAULT_PREFERENCES``. ``SKIP`` is only ever applied when the candidate's
own facts confirm the gap; an unknown fact is never escalated past
``REVIEW``.
"""

from __future__ import annotations

ACTIONS = ('SKIP', 'REVIEW', 'IGNORE')

DEFAULT_PREFERENCES: dict[str, str] = {
    # Posting limits applicants to citizens and/or permanent residents.
    'citizen_or_resident_only': 'REVIEW',
    # Posting states the employer will not sponsor a work visa or permit.
    'no_sponsorship': 'REVIEW',
    # Posting requires an existing, unrestricted right to work.
    'unrestricted_work_rights_required': 'REVIEW',
    # Posting prefers local candidates or existing authorization.
    'local_candidates_preferred': 'IGNORE',
    # Job country is outside the candidate's authorized countries and the
    # posting says nothing about sponsorship.
    'work_authorization_not_stated': 'REVIEW',
    # A required language is confirmed absent from the candidate's profile.
    'required_language_missing': 'SKIP',
    # A required language or proficiency level cannot be verified.
    'required_language_unverified': 'REVIEW',
}


def load_preferences(strategy: dict | None) -> dict[str, str]:
    """Merge user preferences over the defaults and validate the actions."""
    merged = dict(DEFAULT_PREFERENCES)
    for key, value in ((strategy or {}).get('eligibility_preferences') or {}).items():
        action = str(value).upper()
        if key in DEFAULT_PREFERENCES and action in ACTIONS:
            merged[key] = action
    return merged


def effect_for(action: str, *, confirmed: bool) -> str:
    """Translate a user action into a hard-gate effect.

    ``confirmed`` says whether the candidate's own facts establish the gap.
    Without confirmation a ``SKIP`` preference is softened to review.
    """
    if action == 'IGNORE':
        return 'NONE'
    if action == 'SKIP' and confirmed:
        return 'CRITICAL_HARD_REQUIREMENT_MISSING'
    return 'MANUAL_REVIEW'
