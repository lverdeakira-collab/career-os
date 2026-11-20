#!/usr/bin/env python3
"""Targeted tests for the location + employment-type Hard Gate.

Uses the bundled candidate_strategy.json (preferred_locations, preferred_employment_types)
so these tests exercise the configured candidate constraints. Job fixtures are
synthetic and isolated per dimension.

Covers:
  LOCATION:    A (preferred-country PASS), B (overseas FAIL), C (missing MANUAL_REVIEW),
               D (multi-country/regional MANUAL_REVIEW)
  EMPLOYMENT:  E (Full-time Permanent PASS), F (Full-time Contract PASS),
               G (Part-time FAIL), H (Internship FAIL), I (unstated MANUAL_REVIEW)
  INTEGRATION: J/K confirm evaluate_hard_gates() end-to-end wiring for one FAIL
               and one PASS case.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


AUTOMATION_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = AUTOMATION_ROOT.parent / '15_Application_Engine'
sys.path.insert(0, str(AUTOMATION_ROOT))

from hard_filters.evaluate_hard_gates import evaluate_hard_gates  # noqa: E402
from hard_filters.location_employment_gates import (  # noqa: E402
    evaluate_employment_type_gate,
    evaluate_location_gate,
)
from eligibility import classify_language_requirements, classify_work_authorization  # noqa: E402


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def job(country: str | None, location: str | None, employment_type: str | None, role_title: str = 'Business Analyst') -> dict:
    return {
        'Company': 'Synthetic Test',
        'Role_Title': role_title,
        'Seniority': 'Analyst',
        'Country': country,
        'Location': location,
        'Employment_Type': employment_type,
        'Required_Experience_Years': 1,
        'Required_Experience_Requirement': {
            'status': 'EXPLICIT', 'minimum_years': 1, 'maximum_years': 2,
            'open_ended_minimum': False, 'approximate': False, 'source_text': '1-2 years',
        },
        'Job_Description_Clean': '',
        'Job_Description_Raw': '',
        'Work_Authorization_Notes': '',
        'Mandatory_Education': [],
    }


def full_gate(profile: dict, strategy: dict, posting: dict) -> dict:
    work_authorization = classify_work_authorization(posting, profile, strategy)
    language_assessments = classify_language_requirements(posting, profile, strategy)
    return evaluate_hard_gates(
        posting, profile, [],
        work_authorization=work_authorization,
        language_assessments=language_assessments,
        strategy=strategy,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--profile', default=str(ENGINE_ROOT / 'candidate_profile.json'))
    parser.add_argument('--strategy', default=str(ENGINE_ROOT / 'candidate_strategy.json'))
    args = parser.parse_args()
    profile = load_json(Path(args.profile))
    strategy = load_json(Path(args.strategy))
    checks = []

    def check(test_id: str, condition: bool, evidence: object) -> None:
        checks.append({'test': test_id, 'status': 'PASS' if condition else 'FAIL', 'evidence': evidence})

    # --- LOCATION ---
    loc_a = evaluate_location_gate(job('Exampleland', 'Example City', 'Full-time'), strategy)
    check('A_preferred_country_role_passes', loc_a['Location_Gate_Status'] == 'PASS', loc_a)

    loc_b = evaluate_location_gate(job('China', 'Shanghai, China', 'Full-time'), strategy)
    check(
        'B_overseas_role_fails',
        loc_b['Location_Gate_Status'] == 'FAIL' and 'China' in (loc_b['Location_Gate_Reason'] or ''),
        loc_b,
    )

    loc_c = evaluate_location_gate(job(None, None, 'Full-time'), strategy)
    check('C_missing_location_manual_review', loc_c['Location_Gate_Status'] == 'MANUAL_REVIEW', loc_c)

    loc_d = evaluate_location_gate(job('Exampleland', 'Example City / Hong Kong', 'Full-time'), strategy)
    check(
        'D_multi_country_regional_not_auto_pass',
        loc_d['Location_Gate_Status'] == 'MANUAL_REVIEW',
        loc_d,
    )
    loc_d2 = evaluate_location_gate(
        job('Exampleland', 'Example City, Exampleland', 'Full-time', role_title='Management Associate Program – SEA Regional Track'),
        strategy,
    )
    check(
        'D2_regional_title_not_auto_pass',
        loc_d2['Location_Gate_Status'] == 'MANUAL_REVIEW',
        loc_d2,
    )

    # --- EMPLOYMENT TYPE ---
    emp_e = evaluate_employment_type_gate(job('Exampleland', 'Example City', 'Full-time Permanent'), strategy)
    check('E_full_time_permanent_passes', emp_e['Employment_Type_Gate_Status'] == 'PASS', emp_e)

    emp_f = evaluate_employment_type_gate(job('Exampleland', 'Example City', 'Full-time Contract'), strategy)
    check(
        'F_full_time_contract_passes_not_rejected_for_non_permanence',
        emp_f['Employment_Type_Gate_Status'] == 'PASS',
        emp_f,
    )

    emp_g = evaluate_employment_type_gate(job('Exampleland', 'Example City', 'Part Time'), strategy)
    check('G_part_time_fails', emp_g['Employment_Type_Gate_Status'] == 'FAIL', emp_g)

    emp_h = evaluate_employment_type_gate(job('Exampleland', 'Example City', 'Intern'), strategy)
    check('H_internship_fails', emp_h['Employment_Type_Gate_Status'] == 'FAIL', emp_h)

    emp_i = evaluate_employment_type_gate(job('Exampleland', 'Example City', None), strategy)
    check('I_unstated_employment_type_manual_review', emp_i['Employment_Type_Gate_Status'] == 'MANUAL_REVIEW', emp_i)

    # --- INTEGRATION (end-to-end through evaluate_hard_gates) ---
    integration_fail = full_gate(profile, strategy, job('China', 'Beijing, China', 'Full-time'))
    check(
        'J_integration_overseas_fails_overall_gate',
        integration_fail['Hard_Gate_Status'] == 'FAIL'
        and integration_fail['Location_Assessment']['Location_Gate_Status'] == 'FAIL',
        integration_fail,
    )

    integration_review = full_gate(profile, strategy, job('Exampleland', 'Example City', 'Part Time'))
    check(
        'K_integration_part_time_contributes_review_or_fail',
        integration_review['Employment_Type_Assessment']['Employment_Type_Gate_Status'] == 'FAIL'
        and integration_review['Hard_Gate_Status'] == 'FAIL',
        integration_review,
    )

    # --- REGRESSION GUARD: contract permanence never used against full-time-only ---
    emp_permanence_only = evaluate_employment_type_gate(job('Exampleland', 'Example City', 'Contract'), strategy)
    check(
        'L_bare_contract_with_no_schedule_word_is_manual_review_not_fail',
        emp_permanence_only['Employment_Type_Gate_Status'] == 'MANUAL_REVIEW',
        emp_permanence_only,
    )

    failed = [item for item in checks if item['status'] == 'FAIL']
    result = {
        'stage': 'location + employment-type Hard Gate targeted tests',
        'tests_passed': len(checks) - len(failed),
        'tests_failed': len(failed),
        'overall_status': 'PASS' if not failed else 'FAIL',
        'checks': checks,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
