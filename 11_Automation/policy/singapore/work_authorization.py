from __future__ import annotations

import re


LOCAL_ONLY_PATTERNS = [
    r'\bsingapore citizens?\s*(?:and|/|or)\s*(?:singapore )?(?:permanent residents?|prs?)\s+only\b',
    r'\bsingapore citizens?\s*/\s*prs?\s+only\b',
    r'\bsingaporeans?\s+only\b',
    r'\bsingapore citizens?\s+only\b',
]
NO_SPONSORSHIP_PATTERNS = [
    r'\bno (?:visa |work pass )?sponsorship (?:is )?(?:available|provided)\b',
    r'\b(?:unable|not able) to (?:provide|offer) (?:visa |work pass )?sponsorship\b',
    r'\b(?:will not|cannot|can not) sponsor\b',
]
UNRESTRICTED_PATTERNS = [
    r'\bmust (?:already )?have unrestricted (?:right|authorization) to work in singapore\b',
    r'\bunrestricted (?:singapore )?work (?:rights?|authorization) required\b',
]
LOCAL_PREFERENCE_PATTERNS = [
    r'\blocal candidates? (?:are )?preferred\b',
    r'\bsingaporeans? (?:are )?preferred\b',
]
AUTHORIZATION_PREFERENCE_PATTERNS = [
    r'\bcandidates? with existing work authori[sz]ation (?:are )?preferred\b',
    r'\bexisting (?:singapore )?work authori[sz]ation (?:is )?(?:preferred|an advantage)\b',
]


def _candidate_status(profile: dict, country: str) -> dict:
    facts = profile.get('work_authorization_facts') or {}
    singapore_status = str(facts.get('singapore_status') or '').upper()
    authorized = {
        str(value).lower()
        for value in (profile.get('location_constraints') or {}).get('work_authorization_countries', [])
    }
    unrestricted = {
        str(value).lower()
        for value in facts.get('unrestricted_work_authorization_countries', [])
    }
    confirmed_absent = {
        str(value).lower()
        for value in facts.get('confirmed_no_work_authorization_countries', [])
    }
    return {
        'singapore_status': singapore_status,
        'country_authorized': country.lower() in authorized,
        'country_unrestricted': country.lower() in unrestricted,
        'country_confirmed_absent': country.lower() in confirmed_absent,
    }


def _matches(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def classify_work_authorization(job: dict, profile: dict) -> dict:
    source_text = ' '.join(
        value for value in [
            job.get('Work_Authorization_Notes') or '',
            job.get('Job_Description_Clean') or '',
        ] if value
    ).strip()
    country = job.get('Country') or ''
    candidate = _candidate_status(profile, country or 'UNKNOWN')
    lower = source_text.lower()

    signal = 'NOT_STATED'
    strength = 'NONE'
    interpretation = 'The job does not state a work-authorization or sponsorship condition.'
    effect = 'NONE'
    confidence = 'HIGH' if source_text else 'MEDIUM'
    review = False

    if _matches(LOCAL_ONLY_PATTERNS, lower):
        signal = 'EXPLICIT_LOCAL_ONLY'
        strength = 'EXPLICIT'
        interpretation = 'The posting explicitly limits applicants to Singapore citizens and/or permanent residents.'
        if candidate['singapore_status'] in {'CITIZEN', 'PERMANENT_RESIDENT', 'PR'}:
            effect = 'NONE'
        elif candidate['singapore_status'] in {'FOREIGN_NATIONAL', 'NOT_CITIZEN_OR_PR'}:
            effect = 'CRITICAL_HARD_REQUIREMENT_MISSING'
        else:
            effect = 'MANUAL_REVIEW'
            review = True
            confidence = 'MEDIUM'
    elif _matches(NO_SPONSORSHIP_PATTERNS, lower):
        signal = 'NO_SPONSORSHIP_AVAILABLE'
        strength = 'STRONG'
        interpretation = 'The employer explicitly states that sponsorship is unavailable.'
        if candidate['country_authorized']:
            effect = 'NONE'
        elif candidate['country_confirmed_absent']:
            effect = 'CRITICAL_HARD_REQUIREMENT_MISSING'
        else:
            effect = 'MANUAL_REVIEW'
            review = True
            confidence = 'MEDIUM'
    elif _matches(UNRESTRICTED_PATTERNS, lower):
        signal = 'UNRESTRICTED_RIGHT_TO_WORK_REQUIRED'
        strength = 'EXPLICIT'
        interpretation = 'The posting requires existing unrestricted Singapore work rights.'
        if candidate['country_unrestricted']:
            effect = 'NONE'
        elif candidate['country_confirmed_absent']:
            effect = 'CRITICAL_HARD_REQUIREMENT_MISSING'
        else:
            effect = 'MANUAL_REVIEW'
            review = True
            confidence = 'MEDIUM'
    elif _matches(LOCAL_PREFERENCE_PATTERNS, lower):
        signal = 'LOCAL_CANDIDATES_PREFERRED'
        strength = 'PREFERENCE'
        interpretation = 'Local status is expressed as a preference, not an explicit eligibility bar.'
        effect = 'PREFERENCE_ONLY'
    elif _matches(AUTHORIZATION_PREFERENCE_PATTERNS, lower):
        signal = 'EXISTING_AUTHORIZATION_PREFERRED'
        strength = 'PREFERENCE'
        interpretation = 'Existing authorization is preferred but not stated as mandatory.'
        effect = 'PREFERENCE_ONLY'
    elif job.get('Sponsorship_Available') == 'NO':
        signal = 'NO_SPONSORSHIP_AVAILABLE'
        strength = 'STRUCTURED'
        interpretation = 'The canonical job record states that sponsorship is unavailable.'
        if candidate['country_authorized']:
            effect = 'NONE'
        elif candidate['country_confirmed_absent']:
            effect = 'CRITICAL_HARD_REQUIREMENT_MISSING'
        else:
            effect = 'MANUAL_REVIEW'
            review = True
            confidence = 'MEDIUM'
    elif not source_text or not any(token in lower for token in ['sponsor', 'authori', 'right to work', 'citizen', 'permanent resident', 'local candidate']):
        signal = 'NOT_STATED'
        strength = 'NONE'
        interpretation = 'Sponsorship is not mentioned; this is unknown, not negative evidence.'
        effect = 'NONE'
        confidence = 'MEDIUM'

    return {
        'work_authorization_signal': signal,
        'signal_strength': strength,
        'source_text': source_text or None,
        'policy_interpretation': interpretation,
        'hard_gate_effect': effect,
        'confidence': confidence,
        'human_review_required': review,
        'candidate_evidence': {
            'country': country or None,
            'country_authorized': candidate['country_authorized'],
            'country_unrestricted': candidate['country_unrestricted'],
            'singapore_status': candidate['singapore_status'] or None,
        },
    }
