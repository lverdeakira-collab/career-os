"""Deterministic fit score. Every number comes from weights.json."""
from __future__ import annotations

from pathlib import Path

from common import load_json


CONFIG_PATH = Path(__file__).with_name('weights.json')
SCORE_CONFIG = load_json(CONFIG_PATH)
SCORE_WEIGHTS = SCORE_CONFIG['components']
EVIDENCE_VALUES = {k: v for k, v in SCORE_CONFIG['evidence_values'].items() if not k.startswith('_')}


def evidence_value(item: dict) -> float:
    """Credit for one gap-matrix item, distinguishing PARTIAL sub-types."""
    category = item.get('Category')
    if category == 'PARTIAL':
        evidence_type = item.get('Evidence_Type')
        if evidence_type == 'TRANSFERABLE':
            return EVIDENCE_VALUES['PARTIAL_TRANSFERABLE']
        if evidence_type == 'RELATED':
            return EVIDENCE_VALUES['PARTIAL_RELATED']
    return EVIDENCE_VALUES[category]


def _weighted_average(items: list[dict], weight: int, credit_if_empty: float) -> int:
    applicable = [item for item in items if item.get('Category') != 'NOT_APPLICABLE']
    if not applicable:
        return round(weight * credit_if_empty)
    return round(weight * sum(evidence_value(item) for item in applicable) / len(applicable))


def _seniority_level(job: dict) -> str | None:
    levels = SCORE_CONFIG['target_seniority']
    seniority = job.get('Seniority')
    if seniority in levels['target']:
        return 'target'
    if seniority in levels['selective']:
        return 'selective'
    return None


def _industry_score(job: dict, profile: dict) -> int:
    points = SCORE_CONFIG['industry_points']
    industry = (job.get('Industry') or '').lower()
    if not industry:
        return points['not_stated']
    exposure = ' '.join(profile.get('industry_exposure') or []).lower()
    if any(token in exposure for token in industry.replace('/', ' ').split() if len(token) > 3):
        return points['matches_candidate_exposure']
    if any(token in industry for token in points['related_domain_keywords']):
        return points['related_domain']
    return points['other']


def _education_score(job: dict) -> int:
    points = SCORE_CONFIG['education_points']
    requirement = (job.get('Education_Requirements') or '').lower()
    if not requirement:
        return points['not_stated']
    if any(term in requirement for term in points['aligned_field_keywords']):
        return points['aligned_field']
    if any(term in requirement for term in points['degree_keywords']):
        return points['degree_any_field']
    return points['other']


def _authorized_countries(profile: dict) -> set[str]:
    facts = profile.get('work_authorization_facts') or {}
    values = list((profile.get('location_constraints') or {}).get('work_authorization_countries', []))
    values += facts.get('authorized_countries', []) + facts.get('citizen_or_resident_countries', [])
    return {str(value).strip().lower() for value in values}


def _confidence(job: dict, gaps: list[dict]) -> str:
    important = [
        bool(job.get('Role_Title')), bool(job.get('Responsibilities')), bool(job.get('Required_Skills')),
        bool(job.get('Country')), bool(job.get('Seniority')), job.get('Required_Experience_Years') is not None,
        bool(job.get('Job_Description_Clean')),
    ]
    count = sum(important)
    unknown_critical = any(
        item.get('Criticality') == 'CRITICAL' and item.get('Category') == 'UNKNOWN'
        for item in gaps
    )
    if count >= 6 and not unknown_critical:
        return 'HIGH'
    return 'MEDIUM' if count >= 4 and not unknown_critical else 'LOW'


def decision_from_score(score: int) -> tuple[str, str]:
    for band in SCORE_CONFIG['decision_bands']:
        if band['minimum'] <= score <= band['maximum']:
            decision = band['decision']
            status = 'SHORTLISTED' if decision in {'PRIORITY_APPLY', 'APPLY'} else ('READY_FOR_REVIEW' if decision == 'REVIEW' else 'SKIPPED')
            return decision, status
    raise ValueError(f'No deterministic decision band covers score {score}.')


def score_job(
    job: dict,
    profile: dict,
    route: dict,
    gate: dict,
    gaps: list[dict],
    strategy: dict | None = None,
) -> dict:
    if sum(SCORE_WEIGHTS.values()) != SCORE_CONFIG['total']:
        raise ValueError('Canonical fit-scoring weights do not sum to 100.')
    role_points = SCORE_CONFIG['role_points']
    empty_credit = SCORE_CONFIG['empty_section_credit']
    split = SCORE_CONFIG['skills_split']
    practical_points = SCORE_CONFIG['practical_points']

    primary = route['Primary_Route']
    route_scores = route['Route_Scores']
    top_route_score = max(route_scores.values()) if route_scores else 0
    if top_route_score >= role_points['function_strong_threshold']:
        function_alignment = role_points['function_strong']
    elif top_route_score >= role_points['function_medium_threshold']:
        function_alignment = role_points['function_medium']
    else:
        function_alignment = role_points['function_weak'] if top_route_score > 0 else 0
    level = _seniority_level(job)
    seniority = {'target': role_points['seniority_target'], 'selective': role_points['seniority_selective']}.get(level, 0)
    responsibilities = job.get('Responsibilities') or []
    responsibility_signal = (
        role_points['responsibilities_two_plus'] if len(responsibilities) >= 2
        else (role_points['responsibilities_one'] if responsibilities else 0)
    )
    role_score = min(
        SCORE_WEIGHTS['Role_Functional_Match'],
        (role_points['has_primary_route'] if primary else 0) + function_alignment + seniority + responsibility_signal,
    )

    responsibility_gaps = [item for item in gaps if item['Requirement_Type'] == 'RESPONSIBILITY']
    experience_score = _weighted_average(responsibility_gaps, SCORE_WEIGHTS['Experience_Evidence'], empty_credit['experience'])

    required_gaps = [item for item in gaps if item['Requirement_Type'] in {'MUST_HAVE', 'REQUIRED'}]
    preferred_gaps = [item for item in gaps if item['Requirement_Type'] == 'PREFERRED']
    required_score = _weighted_average(required_gaps, split['required'], empty_credit['required_skills'])
    preferred_score = _weighted_average(preferred_gaps, split['preferred'], empty_credit['preferred_skills'])
    skills_score = min(SCORE_WEIGHTS['Skills_Match'], required_score + preferred_score)

    industry_score = _industry_score(job, profile)
    education_score = _education_score(job)

    country = (job.get('Country') or '').strip().lower()
    preferred_locations = {str(value).strip().lower() for value in (strategy or {}).get('preferred_locations', [])}
    if country and (country in _authorized_countries(profile) or country in preferred_locations):
        location_points = practical_points['location_match']
    else:
        location_points = practical_points['location_unknown'] if not country else 0
    seniority_points = {'target': practical_points['seniority_target'], 'selective': practical_points['seniority_selective']}.get(level, 0)
    practical_score = min(
        SCORE_WEIGHTS['Practical_Fit'],
        location_points + seniority_points + (practical_points['has_primary_route'] if primary else 0),
    )

    breakdown = {
        'Role_Functional_Match': role_score,
        'Experience_Evidence': experience_score,
        'Skills_Match': skills_score,
        'Industry_Match': industry_score,
        'Education_Match': education_score,
        'Practical_Fit': practical_score,
    }
    fit_score = sum(breakdown.values())
    confidence = _confidence(job, gaps)

    circuit_triggered = bool((gate.get('Circuit_Breaker') or {}).get('Triggered'))
    if circuit_triggered or gate['Hard_Gate_Status'] == 'FAIL':
        decision, status = 'SKIP', 'HARD_GATE_FAILED'
    elif gate['Hard_Gate_Status'] == 'MANUAL_REVIEW':
        decision, status = 'REVIEW', 'READY_FOR_REVIEW'
    else:
        decision, status = decision_from_score(fit_score)
    score_band_decision = decision_from_score(fit_score)[0]

    matches = [item['Requirement'] for item in gaps if item['Category'] in {'MATCHED', 'PARTIAL'}]
    gap_items = [item for item in gaps if item['Category'] in {'MISSING', 'UNKNOWN'}]
    if primary:
        matches.insert(0, f'Primary route: {primary}')
    return {
        'Fit_Score': fit_score,
        'Fit_Score_Breakdown': breakdown,
        'Score_Band_Decision': score_band_decision,
        'Assessment_Confidence': confidence,
        'Decision': decision,
        'Status': status,
        'Top_Matches': matches[:5],
        'Gaps': gaps,
        'Gap_Count': len(gap_items),
        'Explanation': {
            'Top_Matches': matches[:5],
            'Main_Gaps': [item['Requirement'] for item in gap_items[:5]],
            'Hard_Gate_Result': gate['Hard_Gate_Status'],
            'Why': (
                'SKIP follows a confirmed critical requirement circuit breaker.'
                if circuit_triggered else
                f'{decision} follows the hard-gate result first, then the deterministic {fit_score}/100 score band ({score_band_decision}).'
            ),
        },
    }
