"""Classify work-authorization signals in a posting against the candidate's
own stated facts and preferences.

Candidate facts (``candidate_profile.json`` -> ``work_authorization_facts``):

- ``authorized_countries``: countries where the candidate may already work
  without sponsorship.
- ``citizen_or_resident_countries``: countries where the candidate is a
  citizen or permanent resident.
- ``requires_sponsorship_countries``: countries where the candidate has
  confirmed they would need sponsorship.

``location_constraints.work_authorization_countries`` is also read as
authorized countries for backward compatibility.
"""

from __future__ import annotations

import re

from .preferences import effect_for, load_preferences


CITIZEN_ONLY_PATTERNS = [
    r'\b(?:[a-z]+ )?citizens?\s*(?:and|/|or|&)\s*(?:[a-z]+ )?(?:permanent residents?|prs?)\s+only\b',
    r'\b(?:[a-z]+ )?citizens?\s+only\b',
    r'\bonly\s+(?:open to\s+)?(?:[a-z]+ )?citizens?\b',
    r'\b[a-z]+ans?\s+only\b',
    r'\bpermanent residents?\s+only\b',
]
NO_SPONSORSHIP_PATTERNS = [
    r'\bno (?:visa |work (?:pass|permit|visa) )?sponsorship (?:is )?(?:available|provided|offered)\b',
    r'\b(?:unable|not able) to (?:provide|offer) (?:visa |work (?:pass|permit|visa) )?sponsorship\b',
    r'\b(?:will not|cannot|can not|do not|does not) sponsor\b',
    r'\bsponsorship (?:is )?not (?:available|provided|offered)\b',
]
UNRESTRICTED_PATTERNS = [
    r'\bmust (?:already )?have (?:the )?(?:unrestricted |full )?right to work\b',
    r'\bunrestricted (?:[a-z]+ )?work (?:rights?|authori[sz]ation) (?:is )?required\b',
    r'\bmust be (?:legally )?(?:authori[sz]ed|eligible) to work\b.{0,40}\bwithout (?:visa )?sponsorship\b',
]
LOCAL_PREFERENCE_PATTERNS = [
    r'\blocal candidates? (?:are |is )?preferred\b',
    r'\b(?:[a-z]+ )?citizens? (?:are )?preferred\b',
    r'\bcandidates? with existing work authori[sz]ation (?:are )?preferred\b',
    r'\bexisting work authori[sz]ation (?:is )?(?:preferred|an advantage)\b',
]
AUTH_TOKENS = ['sponsor', 'authori', 'right to work', 'citizen', 'permanent resident', 'local candidate', 'work permit', 'visa']


def _lower_set(values) -> set[str]:
    return {str(value).strip().lower() for value in values or [] if str(value).strip()}


def candidate_status(profile: dict, country: str) -> dict:
    facts = profile.get('work_authorization_facts') or {}
    authorized = _lower_set(facts.get('authorized_countries')) | _lower_set(
        (profile.get('location_constraints') or {}).get('work_authorization_countries')
    )
    citizen = _lower_set(facts.get('citizen_or_resident_countries'))
    needs_sponsorship = _lower_set(facts.get('requires_sponsorship_countries'))
    key = (country or '').strip().lower()
    return {
        'country_authorized': key in authorized or key in citizen,
        'country_citizen_or_resident': key in citizen,
        'country_requires_sponsorship': key in needs_sponsorship,
    }


def _matches(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def classify_work_authorization(job: dict, profile: dict, strategy: dict | None = None) -> dict:
    preferences = load_preferences(strategy)
    source_text = ' '.join(
        value for value in [job.get('Work_Authorization_Notes') or '', job.get('Job_Description_Clean') or ''] if value
    ).strip()
    lower = source_text.lower()
    country = job.get('Country') or ''
    candidate = candidate_status(profile, country)

    signal, strength, preference_key = 'NOT_STATED', 'NONE', None
    interpretation = 'The posting does not state a work-authorization or sponsorship condition.'
    satisfied = False
    confirmed_gap = False

    if _matches(CITIZEN_ONLY_PATTERNS, lower):
        signal, strength, preference_key = 'CITIZEN_OR_RESIDENT_ONLY', 'EXPLICIT', 'citizen_or_resident_only'
        interpretation = 'The posting limits applicants to citizens and/or permanent residents.'
        satisfied = candidate['country_citizen_or_resident']
        confirmed_gap = candidate['country_requires_sponsorship']
    elif _matches(NO_SPONSORSHIP_PATTERNS, lower) or job.get('Sponsorship_Available') == 'NO':
        signal, preference_key = 'NO_SPONSORSHIP_AVAILABLE', 'no_sponsorship'
        strength = 'STRONG' if _matches(NO_SPONSORSHIP_PATTERNS, lower) else 'STRUCTURED'
        interpretation = 'The employer states that sponsorship is unavailable.'
        satisfied = candidate['country_authorized']
        confirmed_gap = candidate['country_requires_sponsorship']
    elif _matches(UNRESTRICTED_PATTERNS, lower):
        signal, strength, preference_key = 'UNRESTRICTED_RIGHT_TO_WORK_REQUIRED', 'EXPLICIT', 'unrestricted_work_rights_required'
        interpretation = 'The posting requires an existing, unrestricted right to work.'
        satisfied = candidate['country_authorized']
        confirmed_gap = candidate['country_requires_sponsorship']
    elif _matches(LOCAL_PREFERENCE_PATTERNS, lower):
        signal, strength, preference_key = 'LOCAL_CANDIDATES_PREFERRED', 'PREFERENCE', 'local_candidates_preferred'
        interpretation = 'Local status or existing authorization is a preference, not a stated requirement.'
        satisfied = candidate['country_authorized']
    elif source_text and any(token in lower for token in AUTH_TOKENS):
        signal, strength = 'AMBIGUOUS', 'WEAK'
        interpretation = 'The posting mentions work authorization, but the condition is unclear.'

    if preference_key is None:
        action = None
        effect = 'MANUAL_REVIEW' if signal == 'AMBIGUOUS' and not candidate['country_authorized'] else 'NONE'
    elif satisfied:
        action = preferences[preference_key]
        effect = 'NONE'
        interpretation += ' The candidate is already authorized for this country.'
    else:
        action = preferences[preference_key]
        effect = effect_for(action, confirmed=confirmed_gap)
        interpretation += f' User preference for this restriction: {action}.'

    return {
        'work_authorization_signal': signal,
        'signal_strength': strength,
        'source_text': source_text or None,
        'policy_interpretation': interpretation,
        'preference_key': preference_key,
        'user_action': action,
        'hard_gate_effect': effect,
        'confidence': 'HIGH' if strength in {'EXPLICIT', 'STRONG', 'STRUCTURED'} else 'MEDIUM',
        'human_review_required': effect == 'MANUAL_REVIEW',
        'candidate_evidence': {'country': country or None, **candidate},
    }
