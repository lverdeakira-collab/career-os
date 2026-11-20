from __future__ import annotations

from datetime import date
from pathlib import Path
import re

from common import load_json


POLICY_PATH = Path(__file__).with_name('mom_ep_policy.json')
FCF_PATH = Path(__file__).with_name('fcf_rules.json')
EP_FEASIBILITY = {
    'EXPLICITLY_INELIGIBLE', 'POLICY_RISK', 'POTENTIALLY_FEASIBLE', 'UNKNOWN', 'HUMAN_REVIEW'
}


def _iso(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def select_active_record(records: list[dict], policy_type: str, as_of: date) -> dict | None:
    eligible = []
    for record in records:
        if record.get('policy_type') != policy_type:
            continue
        start, end = _iso(record.get('effective_from')), _iso(record.get('effective_to'))
        if start and as_of < start:
            continue
        if end and as_of > end:
            continue
        eligible.append(record)
    if not eligible:
        return None
    return sorted(eligible, key=lambda item: item.get('effective_from') or '')[-1]


def _parse_salary(value: str | None) -> tuple[float | None, float | None]:
    if not value:
        return None, None
    numbers = []
    for token in re.findall(r'(?<!\w)(\d{1,3}(?:,\d{3})+|\d{4,5})(?!\w)', value):
        numbers.append(float(token.replace(',', '')))
    if not numbers:
        return None, None
    return min(numbers), max(numbers)


def _salary_threshold(record: dict, sector: str | None, candidate_age: int | None) -> tuple[int | None, str]:
    if sector not in record['sectors']:
        return None, 'Sector classification is unavailable or not authoritative.'
    if candidate_age is None:
        return None, 'Candidate age is unavailable; the EP qualifying salary is age-dependent.'
    bounded_age = min(record['age_cap'], max(record['age_floor'], candidate_age))
    return record['sectors'][sector][str(bounded_age)], f'Age {candidate_age} uses policy table age {bounded_age}.'


def evaluate_singapore_employment_policy(
    job: dict,
    profile: dict,
    strategy: dict | None = None,
    *,
    as_of: str | date | None = None,
    sector: str | None = None,
    candidate_age: int | None = None,
    policy_data: dict | None = None,
    fcf_data: dict | None = None,
) -> dict:
    assessment_date = _iso(as_of) if isinstance(as_of, str) else (as_of or date.today())
    policy_data = policy_data or load_json(POLICY_PATH)
    fcf_data = fcf_data or load_json(FCF_PATH)
    salary_policy = select_active_record(policy_data['records'], 'EP_QUALIFYING_SALARY', assessment_date)
    compass_policy = select_active_record(policy_data['records'], 'COMPASS', assessment_date)
    quota_policy = select_active_record(policy_data['records'], 'EP_QUOTA_AND_LEVY', assessment_date)
    fcf_policy = select_active_record(fcf_data['records'], 'FCF_ADVERTISING_REQUIREMENT', assessment_date)
    advertised_min, advertised_max = _parse_salary(job.get('Salary'))
    personal_floor = (strategy or {}).get('personal_salary_floor_sgd')
    reasons = []
    review = False

    if salary_policy is None:
        feasibility = 'HUMAN_REVIEW'
        threshold = None
        reasons.append('No active EP qualifying-salary policy exists for the assessment date; fail closed for policy selection.')
        review = True
    else:
        threshold, threshold_note = _salary_threshold(salary_policy, sector, candidate_age)
        reasons.append(threshold_note)
        universal_floor = min(min(values.values()) for values in salary_policy['sectors'].values())
        universal_ceiling = max(max(values.values()) for values in salary_policy['sectors'].values())
        if advertised_max is not None and advertised_max < universal_floor:
            feasibility = 'EXPLICITLY_INELIGIBLE'
            reasons.append(f'Advertised maximum SGD {advertised_max:g} is below the policy-wide minimum SGD {universal_floor:g}.')
        elif threshold is not None and advertised_max is not None and advertised_max < threshold:
            feasibility = 'EXPLICITLY_INELIGIBLE'
            reasons.append(f'Advertised maximum SGD {advertised_max:g} is below the applicable qualifying salary SGD {threshold:g}.')
        elif threshold is not None and advertised_min is not None and advertised_min >= threshold:
            feasibility = 'POTENTIALLY_FEASIBLE'
            reasons.append('Advertised minimum meets Stage 1 salary; COMPASS and employer-side checks remain outstanding.')
            review = True
        elif advertised_min is not None and advertised_min >= universal_ceiling:
            feasibility = 'POTENTIALLY_FEASIBLE'
            reasons.append('Advertised minimum clears every age/sector value in the selected salary policy; COMPASS remains outstanding.')
            review = True
        elif advertised_min is None:
            feasibility = 'UNKNOWN'
            reasons.append('Advertised salary is unavailable; absence of salary evidence is not ineligibility.')
            review = True
        else:
            feasibility = 'HUMAN_REVIEW'
            reasons.append('Salary is present but sector and/or age evidence is insufficient for a definitive Stage 1 assessment.')
            review = True

    if compass_policy is None:
        reasons.append('No active COMPASS policy record is available.')
        review = True
    else:
        reasons.append('Employer-side COMPASS inputs are not available in ordinary job-posting data; no EP_ELIGIBLE=true output is permitted.')
        review = True

    if fcf_policy is None:
        fcf_status = 'HUMAN_REVIEW'
        reasons.append('No active FCF record is available.')
        review = True
    elif (job.get('Source') or '').lower().startswith('mycareersfuture'):
        fcf_status = 'EVIDENCE_PRESENT'
    else:
        fcf_status = 'UNKNOWN'
        reasons.append('No visible MyCareersFuture evidence is stored; exemptions, timing, and employer-side evidence remain possible.')

    if quota_policy and quota_policy.get('quota_required') is False:
        reasons.append('Company size is not used as an EP rejection heuristic; MOM records no EP quota or levy requirement.')

    assert feasibility in EP_FEASIBILITY
    return {
        'jurisdiction': 'Singapore',
        'assessment_date': assessment_date.isoformat(),
        'ep_feasibility': feasibility,
        'ep_eligible': None,
        'human_review_required': review,
        'advertised_salary_sgd': {'minimum': advertised_min, 'maximum': advertised_max},
        'candidate_personal_salary_floor_sgd': personal_floor,
        'salary_preference_independent_from_policy': True,
        'selected_ep_salary_policy_id': salary_policy.get('policy_id') if salary_policy else None,
        'selected_ep_salary_policy_version': salary_policy.get('policy_version') if salary_policy else None,
        'sector': sector,
        'candidate_age': candidate_age,
        'applicable_ep_qualifying_salary_sgd': threshold,
        'compass_status': 'UNKNOWN' if compass_policy else 'HUMAN_REVIEW',
        'compass_policy_id': compass_policy.get('policy_id') if compass_policy else None,
        'fcf_status': fcf_status,
        'fcf_policy_id': fcf_policy.get('policy_id') if fcf_policy else None,
        'reasons': reasons,
    }
