from __future__ import annotations

from gap_analysis.circuit_breaker import evaluate_circuit_breaker
from hard_filters.experience_semantics import evaluate_experience_gate
from hard_filters.location_employment_gates import (
    evaluate_employment_type_gate,
    evaluate_location_gate,
)
from policy.singapore.language_classifier import classify_language_requirements
from policy.singapore.work_authorization import classify_work_authorization
from resume_router.route_resume import is_incompatible_engineering


def evaluate_hard_gates(
    job: dict,
    profile: dict,
    gaps: list[dict] | None = None,
    *,
    work_authorization: dict | None = None,
    language_assessments: list[dict] | None = None,
    employment_policy: dict | None = None,
    strategy: dict | None = None,
) -> dict:
    failures = []
    reviews = []
    gaps = gaps or []
    work_authorization = work_authorization or classify_work_authorization(job, profile)
    language_assessments = language_assessments or classify_language_requirements(job, profile)
    circuit_breaker = evaluate_circuit_breaker(gaps)

    if is_incompatible_engineering(job):
        failures.append('Fundamentally incompatible pure software/ML engineering profession.')

    seniority = job.get('Seniority')
    if seniority in {'Manager', 'Senior Manager', 'Director', 'Executive'}:
        failures.append(f'Seniority {seniority} is outside the approved early-career scope.')
    elif seniority == 'Senior Associate':
        failures.append('Senior Associate is outside the normal target range.')
    elif seniority == 'Associate':
        reviews.append('Associate roles are selective and require manual evidence review.')
    elif seniority is None:
        reviews.append('Seniority is not specified.')

    experience_gate = evaluate_experience_gate(job)
    experience_reason = experience_gate['Hard_Gate_Reason']
    if experience_gate['Hard_Gate_Status'] == 'FAIL':
        failures.append(experience_reason)
    elif experience_gate['Hard_Gate_Status'] == 'MANUAL_REVIEW':
        reviews.append(experience_reason)

    location_gate = evaluate_location_gate(job, strategy)
    if location_gate['Location_Gate_Status'] == 'FAIL':
        failures.append(location_gate['Location_Gate_Reason'])
    elif location_gate['Location_Gate_Status'] == 'MANUAL_REVIEW':
        reviews.append(location_gate['Location_Gate_Reason'])

    employment_type_gate = evaluate_employment_type_gate(job, strategy)
    if employment_type_gate['Employment_Type_Gate_Status'] == 'FAIL':
        failures.append(employment_type_gate['Employment_Type_Gate_Reason'])
    elif employment_type_gate['Employment_Type_Gate_Status'] == 'MANUAL_REVIEW':
        reviews.append(employment_type_gate['Employment_Type_Gate_Reason'])

    country = job.get('Country')
    authorized = {
        str(value).lower()
        for value in (profile.get('location_constraints') or {}).get('work_authorization_countries', [])
    }
    if not country:
        reviews.append('Country/location eligibility is unknown.')
    elif country.lower() not in authorized and work_authorization['work_authorization_signal'] == 'NOT_STATED':
        reviews.append(f'Work authorization for {country} is not established; sponsorship is not stated.')

    if work_authorization['hard_gate_effect'] == 'CRITICAL_HARD_REQUIREMENT_MISSING':
        failures.append(work_authorization['policy_interpretation'])
    elif work_authorization['human_review_required']:
        reviews.append(work_authorization['policy_interpretation'])

    for assessment in language_assessments:
        if assessment['hard_gate_effect'] == 'CRITICAL_HARD_REQUIREMENT_MISSING':
            failures.append(f"Mandatory language confirmed missing: {assessment['language']}.")
        elif assessment['hard_gate_effect'] == 'MANUAL_REVIEW':
            reviews.append(f"Language evidence requires review: {assessment['language']}.")

    for gap in gaps:
        if gap.get('Criticality') != 'CRITICAL':
            continue
        category = gap.get('Category')
        requirement_type = gap.get('Requirement_Type')
        if category == 'MISSING':
            failures.append(f"Critical requirement confirmed missing: {gap.get('Requirement')}.")
        elif category in {'UNKNOWN', 'PARTIAL'} and requirement_type in {'MUST_HAVE', 'REQUIRED', 'LICENSE'}:
            reviews.append(f"Critical requirement requires evidence review: {gap.get('Requirement')}.")

    education_text = ' '.join(job.get('Mandatory_Education') or []).lower()
    if education_text and any(term in education_text for term in ['computer science only', 'engineering license', 'medical degree', 'law degree']):
        failures.append('Mandatory education establishes a fundamentally incompatible profession.')

    facts = profile.get('work_authorization_facts') or {}
    requires_sponsorship = facts.get('requires_sponsorship_for_singapore')
    if employment_policy and employment_policy.get('ep_feasibility') == 'EXPLICITLY_INELIGIBLE':
        if requires_sponsorship is True:
            failures.append('Verified sponsorship need plus an explicitly unmet active EP salary rule.')
        elif country and country.lower() not in authorized:
            reviews.append('EP salary evidence is explicitly below threshold, but Candidate Truth does not establish that EP sponsorship is required.')
    elif employment_policy and employment_policy.get('human_review_required') and requires_sponsorship is True:
        reviews.append('Singapore employment-policy feasibility requires human review.')

    failures = list(dict.fromkeys(failures))
    reviews = list(dict.fromkeys(reviews))
    if circuit_breaker['Triggered'] and not failures:
        failures.append('Critical Hard Requirement Circuit Breaker triggered.')
    if failures:
        status = 'FAIL'
    elif reviews:
        status = 'MANUAL_REVIEW'
    else:
        status = 'PASS'
    return {
        'Hard_Gate_Status': status,
        'Hard_Gate_Reasons': failures + reviews if (failures or reviews) else ['All explicit hard constraints passed.'],
        'Circuit_Breaker': circuit_breaker,
        'Experience_Interpretation': experience_gate,
        'Work_Authorization_Assessment': work_authorization,
        'Language_Assessments': language_assessments,
        'Location_Assessment': location_gate,
        'Employment_Type_Assessment': employment_type_gate,
    }
