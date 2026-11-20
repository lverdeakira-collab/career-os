from __future__ import annotations

import re


SEMANTIC_TYPES = {
    'UNKNOWN',
    'EXACT',
    'APPROXIMATE',
    'BOUNDED_RANGE',
    'OPEN_MINIMUM',
    'LEGACY_SCALAR',
}


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if value >= 0 else None


def _valid_metadata(value: object) -> bool:
    if not isinstance(value, dict) or value.get('status') not in {'EXPLICIT', 'UNKNOWN'}:
        return False
    if not isinstance(value.get('open_ended_minimum'), bool) or not isinstance(value.get('approximate'), bool):
        return False
    minimum = _number(value.get('minimum_years'))
    maximum = _number(value.get('maximum_years'))
    if value['status'] == 'UNKNOWN':
        return minimum is None and maximum is None
    if minimum is None:
        return False
    if maximum is not None and maximum < minimum:
        return False
    if value['open_ended_minimum'] and (maximum is not None or value['approximate']):
        return False
    if value['approximate'] and maximum is not None:
        return False
    return True


def interpret_experience_requirement(job: dict) -> dict:
    """Return one lossless, deterministic view of the job's experience requirement.

    Valid canonical metadata is authoritative. The scalar field is used only when
    metadata is absent or invalid so historical normalized records remain usable.
    """
    metadata = job.get('Required_Experience_Requirement')
    if _valid_metadata(metadata):
        minimum = _number(metadata.get('minimum_years'))
        maximum = _number(metadata.get('maximum_years'))
        if metadata['status'] == 'UNKNOWN':
            semantic_type = 'UNKNOWN'
        elif metadata['approximate']:
            semantic_type = 'APPROXIMATE'
        elif metadata['open_ended_minimum']:
            semantic_type = 'OPEN_MINIMUM'
        elif maximum is not None:
            semantic_type = 'BOUNDED_RANGE'
        else:
            semantic_type = 'EXACT'
        return {
            'Semantic_Type': semantic_type,
            'Minimum_Years': minimum,
            'Maximum_Years': maximum,
            'Open_Ended_Minimum': metadata['open_ended_minimum'],
            'Approximate': metadata['approximate'],
            'Source_Text': metadata.get('source_text'),
            'Source': 'CANONICAL_METADATA',
        }

    legacy = _number(job.get('Required_Experience_Years'))
    if legacy is None:
        return {
            'Semantic_Type': 'UNKNOWN',
            'Minimum_Years': None,
            'Maximum_Years': None,
            'Open_Ended_Minimum': False,
            'Approximate': False,
            'Source_Text': None,
            'Source': 'NO_RELIABLE_REQUIREMENT',
        }
    return {
        'Semantic_Type': 'LEGACY_SCALAR',
        'Minimum_Years': legacy,
        'Maximum_Years': None,
        'Open_Ended_Minimum': False,
        'Approximate': False,
        'Source_Text': None,
        'Source': 'LEGACY_SCALAR_FALLBACK',
    }


def _years(value: float) -> str:
    return f'{value:g}'


def _label(requirement: dict) -> str:
    semantic_type = requirement['Semantic_Type']
    minimum = requirement['Minimum_Years']
    maximum = requirement['Maximum_Years']
    if semantic_type == 'OPEN_MINIMUM':
        return f'{_years(minimum)}+ years'
    if semantic_type == 'BOUNDED_RANGE':
        return f'{_years(minimum)}–{_years(maximum)} years'
    if semantic_type == 'APPROXIMATE':
        return f'approximately {_years(minimum)} years'
    if semantic_type == 'EXACT':
        return f'{_years(minimum)} years'
    if semantic_type == 'LEGACY_SCALAR':
        return f'{_years(minimum)} years'
    return 'unknown experience requirement'


def evaluate_experience_gate(job: dict) -> dict:
    requirement = interpret_experience_requirement(job)
    semantic_type = requirement['Semantic_Type']
    minimum = requirement['Minimum_Years']
    label = _label(requirement)

    if semantic_type == 'UNKNOWN':
        status = 'MANUAL_REVIEW'
        reason = 'Mandatory experience years are not stated.'
    elif semantic_type == 'APPROXIMATE':
        if minimum <= 2:
            status = 'PASS'
            reason = None
        else:
            status = 'MANUAL_REVIEW'
            reason = f'{label.capitalize()} is stated; the approximate qualifier requires manual review.'
    elif semantic_type == 'EXACT':
        if minimum <= 2:
            status = 'PASS'
            reason = None
        else:
            status = 'MANUAL_REVIEW'
            reason = f'{label.capitalize()} is stated; the exact requirement requires manual review under the existing policy.'
    elif semantic_type in {'OPEN_MINIMUM', 'BOUNDED_RANGE'}:
        if minimum >= 5:
            status = 'FAIL'
            reason = (
                f'{_years(minimum)}+ years required; normal early-career hard-fail threshold is 5+ years.'
                if semantic_type == 'OPEN_MINIMUM'
                else f'{label.capitalize()} required; its explicit minimum is within the existing 5+ hard-fail policy.'
            )
        elif minimum >= 3:
            status = 'MANUAL_REVIEW'
            reason = f'{label.capitalize()} required; review whether graduate/equivalent experience is accepted.'
        elif minimum > 2:
            status = 'MANUAL_REVIEW'
            reason = f'{label.capitalize()} required; evidence needs manual review.'
        else:
            status = 'PASS'
            reason = None
    else:  # LEGACY_SCALAR: preserve the historical scalar behavior exactly.
        if minimum >= 5:
            status = 'FAIL'
            reason = f'{_years(minimum)}+ years required; normal early-career hard-fail threshold is 5+ years.'
        elif minimum >= 3:
            status = 'MANUAL_REVIEW'
            reason = f'{_years(minimum)} years required; review whether graduate/equivalent experience is accepted.'
        elif minimum > 2:
            status = 'MANUAL_REVIEW'
            reason = f'{_years(minimum)} years required; evidence needs manual review.'
        else:
            status = 'PASS'
            reason = None
    return {**requirement, 'Hard_Gate_Status': status, 'Hard_Gate_Reason': reason}


def classify_early_career(job: dict) -> dict:
    requirement = interpret_experience_requirement(job)
    semantic_type = requirement['Semantic_Type']
    minimum = requirement['Minimum_Years']
    maximum = requirement['Maximum_Years']
    label = _label(requirement)
    seniority = job.get('Seniority')
    title = (job.get('Role_Title') or '').lower()
    jd_text = (job.get('Job_Description_Clean') or '').lower()
    explicit_fresh_graduate = bool(re.search(r'fresh graduates?|upcoming graduates?', jd_text))

    if seniority in {'Manager', 'Senior Manager', 'Director', 'Executive', 'Senior Associate'}:
        classification, reason = 'OVER_SENIOR', f'{seniority} is outside the early-career target range.'
    elif semantic_type == 'OPEN_MINIMUM' and minimum >= 5:
        classification, reason = 'OVER_SENIOR', f'Frozen evidence establishes an open minimum of {label}.'
    elif semantic_type == 'BOUNDED_RANGE' and minimum >= 5:
        classification, reason = 'OVER_SENIOR', f'Frozen evidence establishes a bounded {label} requirement.'
    elif semantic_type == 'APPROXIMATE' and minimum >= 5:
        classification, reason = 'STRETCH', f'Frozen evidence states {label}; the approximation requires human review.'
    elif semantic_type == 'EXACT' and minimum >= 5:
        classification, reason = 'STRETCH', f'Frozen evidence states exactly {label}; the role is outside the normal target but not an open minimum.'
    elif semantic_type == 'LEGACY_SCALAR' and minimum >= 5:
        classification, reason = 'OVER_SENIOR', f'Frozen evidence establishes an experience anchor/minimum of {_years(minimum)} years.'
    elif explicit_fresh_graduate:
        classification, reason = 'TARGET', 'The frozen JD explicitly welcomes fresh or upcoming graduates.'
    elif 'experienced professional' in title and semantic_type == 'UNKNOWN':
        classification, reason = 'STRETCH', 'The title explicitly targets experienced professionals but does not state a numeric requirement.'
    elif minimum is not None and minimum >= 3:
        reason = (
            f'Frozen evidence establishes an experience anchor/minimum of {_years(minimum)} years.'
            if semantic_type == 'LEGACY_SCALAR'
            else f'Frozen evidence establishes {label}.'
        )
        classification = 'STRETCH'
    elif semantic_type == 'BOUNDED_RANGE' and minimum <= 1 and maximum is not None and maximum <= 2:
        classification, reason = 'TARGET', f'Frozen evidence establishes a low bounded requirement of {label}.'
    elif minimum is not None and minimum <= 1:
        reason = (
            f'Frozen evidence establishes a {_years(minimum)}-year minimum/anchor.'
            if semantic_type == 'LEGACY_SCALAR'
            else f'Frozen evidence establishes {label}.'
        )
        classification = 'TARGET'
    elif minimum is not None and minimum <= 2:
        reason = (
            f'Frozen evidence establishes a {_years(minimum)}-year minimum/anchor.'
            if semantic_type == 'LEGACY_SCALAR'
            else f'Frozen evidence establishes {label}.'
        )
        classification = 'ACCEPTABLE'
    elif seniority in {'Intern', 'Graduate', 'Entry Level'}:
        classification, reason = 'TARGET', f'{seniority} is directly aligned with the early-career target.'
    elif seniority in {'Analyst', 'Junior Associate'}:
        classification, reason = 'ACCEPTABLE', f'{seniority} is within the target range; years remain unknown.'
    elif seniority == 'Associate':
        classification, reason = 'STRETCH', 'Associate is selective and requires human review.'
    else:
        classification, reason = 'UNKNOWN', 'No conclusive seniority or numeric experience evidence is available.'
    return {
        'Classification': classification,
        'Reason': reason,
        'Experience_Interpretation': requirement,
    }
