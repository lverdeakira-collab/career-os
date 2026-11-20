from __future__ import annotations

import re


# Country names used only to flag a preferred-country match as possibly
# regional/multi-country. The candidate's own preferred locations are removed
# from this list at evaluation time, so no country is assumed as "home".
COUNTRY_MARKERS = [
    'singapore', 'china', 'hong kong', 'malaysia', 'united states', 'united kingdom', 'japan',
    'thailand', 'indonesia', 'vietnam', 'philippines', 'india', 'australia', 'taiwan', 'korea',
    'canada', 'germany', 'france', 'netherlands', 'ireland', 'united arab emirates',
]
REGIONAL_MARKERS = [
    'apac', 'emea', 'sea region', 'asean', 'regional', 'multiple locations',
    'various locations', 'multi-country', 'multiple countries', 'sea regional',
]

SCHEDULE_PATTERNS = {
    'FULL_TIME': r'\bfull[\s-]?time\b',
    'PART_TIME': r'\bpart[\s-]?time\b',
    'INTERNSHIP': r'\bintern(?:ship)?\b',
    'FREELANCE_CASUAL': r'\bfreelance\b|\bcasual\b|\bgig\b',
}
PERMANENCE_PATTERNS = {
    'CONTRACT': r'\bcontract\b',
    'PERMANENT': r'\bpermanent\b',
    'TEMPORARY_FIXED_TERM': r'\btemp(?:orary)?\b|\bfixed[\s-]?term\b',
}
SCHEDULE_TAGS = frozenset(SCHEDULE_PATTERNS)


def _employment_type_tags(raw: str | None) -> set[str]:
    """Tag an Employment_Type string on two independent axes: schedule
    (full-time/part-time/internship/freelance) and permanence
    (contract/permanent/temporary). Permanence tags are informational only —
    evaluate_employment_type_gate() never lets them drive PASS/FAIL, so a
    "Full-time Contract" role is never rejected for not being permanent.
    """
    text = (raw or '').lower()
    tags = set()
    for tag, pattern in SCHEDULE_PATTERNS.items():
        if re.search(pattern, text):
            tags.add(tag)
    for tag, pattern in PERMANENCE_PATTERNS.items():
        if re.search(pattern, text):
            tags.add(tag)
    return tags


def evaluate_location_gate(job: dict, strategy: dict | None) -> dict:
    """Location dimension of the Hard Gate: does this job match the
    candidate's target location(s) (candidate_strategy.preferred_locations)?

    Consumes the already-normalized Country field rather than re-parsing raw
    location text (Country is produced once, upstream, by
    job_discovery/normalize_source.py._country()). Location text is used only
    as a supplementary signal to catch a posting that names a preferred
    country but is actually multi-country/regional — never to override or
    re-derive Country itself.

    No-ops (PASS, no reason) when candidate_strategy.preferred_locations is
    not configured, so this function has zero effect unless the candidate has
    stated a target location.
    """
    preferred = {str(p).strip().lower() for p in (strategy or {}).get('preferred_locations') or []}
    if not preferred:
        return {'Location_Gate_Status': 'PASS', 'Location_Gate_Reason': None}

    country = job.get('Country')
    if not country:
        return {
            'Location_Gate_Status': 'MANUAL_REVIEW',
            'Location_Gate_Reason': 'Location/country is not stated.',
        }

    if str(country).strip().lower() not in preferred:
        return {
            'Location_Gate_Status': 'FAIL',
            'Location_Gate_Reason': (
                f"Role is based in {country}, outside the candidate's target location(s) "
                f"({', '.join(sorted(preferred)) or 'none configured'})."
            ),
        }

    combined_text = ' '.join(
        str(value) for value in (job.get('Location'), job.get('Role_Title')) if value
    ).lower()
    other_country_hits = sorted({
        marker for marker in COUNTRY_MARKERS
        if marker in combined_text and marker != str(country).strip().lower() and marker not in preferred
    })
    regional_hits = sorted({marker for marker in REGIONAL_MARKERS if marker in combined_text})
    if other_country_hits or regional_hits:
        return {
            'Location_Gate_Status': 'MANUAL_REVIEW',
            'Location_Gate_Reason': (
                f'Country is {country}, but the posting text suggests a multi-country/regional '
                f'role (signals: {other_country_hits + regional_hits}); not an automatic pass.'
            ),
        }

    return {'Location_Gate_Status': 'PASS', 'Location_Gate_Reason': None}


def evaluate_employment_type_gate(job: dict, strategy: dict | None) -> dict:
    """Employment-type/schedule dimension of the Hard Gate: is this a
    full-time role (candidate_strategy.preferred_employment_types)?

    Full-time is checked strictly on the SCHEDULE axis (full-time vs
    part-time vs internship vs freelance/casual). Contract permanence
    (contract/permanent/temporary/fixed-term) is a separate, independent axis
    and is never used to fail a role — a "Full-time Contract" or "Full-time
    Fixed-term" posting passes this gate exactly like "Full-time Permanent".

    No-ops (PASS, no reason) when candidate_strategy.preferred_employment_types
    does not contain "full-time" (case/spacing-insensitive), so this function
    has zero effect unless the candidate has stated a full-time-only
    preference.
    """
    preferred = {
        re.sub(r'[\s-]', '', str(p).strip().lower())
        for p in (strategy or {}).get('preferred_employment_types') or []
    }
    if 'fulltime' not in preferred:
        return {
            'Employment_Type_Gate_Status': 'PASS',
            'Employment_Type_Gate_Reason': None,
            'Employment_Type_Tags': [],
        }

    tags = _employment_type_tags(job.get('Employment_Type'))
    schedule_tags = tags & SCHEDULE_TAGS

    if not schedule_tags:
        return {
            'Employment_Type_Gate_Status': 'MANUAL_REVIEW',
            'Employment_Type_Gate_Reason': (
                'Employment type/schedule is not stated; candidate strategy requires full-time only.'
            ),
            'Employment_Type_Tags': sorted(tags),
        }

    if schedule_tags == {'FULL_TIME'}:
        return {
            'Employment_Type_Gate_Status': 'PASS',
            'Employment_Type_Gate_Reason': None,
            'Employment_Type_Tags': sorted(tags),
        }

    if len(schedule_tags) > 1:
        return {
            'Employment_Type_Gate_Status': 'MANUAL_REVIEW',
            'Employment_Type_Gate_Reason': (
                f'Employment type text carries contradictory schedule signals '
                f'({sorted(schedule_tags)}); candidate strategy requires full-time only.'
            ),
            'Employment_Type_Tags': sorted(tags),
        }

    reason_by_tag = {
        'PART_TIME': 'Part-time role; candidate strategy requires full-time only.',
        'INTERNSHIP': 'Internship; candidate strategy requires full-time (non-internship) employment.',
        'FREELANCE_CASUAL': 'Freelance/casual/gig role; candidate strategy requires full-time only.',
    }
    (only_tag,) = schedule_tags
    return {
        'Employment_Type_Gate_Status': 'FAIL',
        'Employment_Type_Gate_Reason': reason_by_tag[only_tag],
        'Employment_Type_Tags': sorted(tags),
    }
