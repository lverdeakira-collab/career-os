from __future__ import annotations

from pathlib import Path

from common import load_json


CONFIG_PATH = Path(__file__).with_name('weights.json')
SCORE_CONFIG = load_json(CONFIG_PATH)
SCORE_WEIGHTS = SCORE_CONFIG['components']

CATEGORY_VALUE = {
    'MATCHED': 1.0,
    'PARTIAL': 0.65,
    'MISSING': 0.0,
    'UNKNOWN': 0.0,
    'NOT_APPLICABLE': 0.0,
    # Historical Stage 3/4 records remain readable.
    'VERIFIED_MATCH': 1.0,
    'PARTIAL_MATCH': 0.75,
    'TRANSFERABLE': 0.55,
}


def _weighted_average(items: list[dict], weight: int, neutral_if_empty: float) -> int:
    applicable = [item for item in items if item.get('Category') != 'NOT_APPLICABLE']
    if not applicable:
        return round(weight * neutral_if_empty)
    def value(item: dict) -> float:
        if item.get('Category') == 'PARTIAL':
            if item.get('Evidence_Type') == 'TRANSFERABLE':
                return 0.55
            if item.get('Evidence_Type') == 'RELATED':
                return 0.75
        return CATEGORY_VALUE[item['Category']]
    return round(weight * sum(value(item) for item in applicable) / len(applicable))


def _industry_score(job: dict, profile: dict) -> int:
    industry = (job.get('Industry') or '').lower()
    if not industry:
        return 5
    exposure = ' '.join(profile.get('industry_exposure') or []).lower()
    if any(token in exposure for token in industry.replace('/', ' ').split() if len(token) > 3):
        return 10
    if any(token in industry for token in ['finance', 'bank', 'investment', 'consumer', 'technology', 'consulting']):
        return 6
    return 3


def _education_score(job: dict) -> int:
    requirement = (job.get('Education_Requirements') or '').lower()
    if not requirement:
        return 6
    if any(term in requirement for term in ['finance', 'economics', 'business', 'commerce', 'quantitative']):
        return 10
    if any(term in requirement for term in ['bachelor', 'degree', 'master']):
        return 8
    return 4


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


def _decision_from_score(score: int) -> tuple[str, str]:
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
    primary = route['Primary_Route']
    route_scores = route['Route_Scores']
    top_route_score = max(route_scores.values()) if route_scores else 0
    role_family = 10 if primary else 0
    function_alignment = 10 if top_route_score >= 12 else (7 if top_route_score >= 7 else (3 if top_route_score > 0 else 0))
    seniority = 6 if job.get('Seniority') in {'Graduate', 'Entry Level', 'Analyst', 'Junior Associate', 'Intern'} else (3 if job.get('Seniority') == 'Associate' else 0)
    responsibility_signal = 4 if len(job.get('Responsibilities') or []) >= 2 else (2 if job.get('Responsibilities') else 0)
    role_score = min(SCORE_WEIGHTS['Role_Functional_Match'], role_family + function_alignment + seniority + responsibility_signal)

    responsibility_gaps = [item for item in gaps if item['Requirement_Type'] == 'RESPONSIBILITY']
    experience_score = _weighted_average(responsibility_gaps, SCORE_WEIGHTS['Experience_Evidence'], 0.40)

    required_gaps = [item for item in gaps if item['Requirement_Type'] in {'MUST_HAVE', 'REQUIRED'}]
    preferred_gaps = [item for item in gaps if item['Requirement_Type'] == 'PREFERRED']
    required_score = _weighted_average(required_gaps, 14, 0.50)
    preferred_score = _weighted_average(preferred_gaps, 6, 1.00)
    skills_score = min(SCORE_WEIGHTS['Skills_Match'], required_score + preferred_score)

    industry_score = _industry_score(job, profile)
    education_score = _education_score(job)
    country = (job.get('Country') or '').lower()
    authorized = {
        str(value).lower()
        for value in (profile.get('location_constraints') or {}).get('work_authorization_countries', [])
    }
    preferred_locations = {str(value).lower() for value in (strategy or {}).get('preferred_locations', [])}
    location_points = 2 if country in authorized else (1 if not country else 0)
    if preferred_locations and country in preferred_locations:
        location_points = 2
    seniority_points = 2 if job.get('Seniority') in {'Graduate', 'Entry Level', 'Analyst', 'Junior Associate', 'Intern'} else (1 if job.get('Seniority') == 'Associate' else 0)
    practical_score = min(SCORE_WEIGHTS['Practical_Fit'], location_points + seniority_points + (1 if primary else 0))

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
        decision, status = _decision_from_score(fit_score)

    matches = [
        item['Requirement'] for item in gaps
        if item['Category'] in {'MATCHED', 'PARTIAL', 'VERIFIED_MATCH', 'PARTIAL_MATCH', 'TRANSFERABLE'}
    ]
    gap_items = [item for item in gaps if item['Category'] in {'MISSING', 'UNKNOWN'}]
    if primary:
        matches.insert(0, f'Primary route: {primary}')
    return {
        'Fit_Score': fit_score,
        'Fit_Score_Breakdown': breakdown,
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
                f'{decision} follows the hard-gate result first, then the deterministic {fit_score}/100 score band.'
            ),
        },
    }
