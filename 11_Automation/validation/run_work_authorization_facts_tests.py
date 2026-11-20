#!/usr/bin/env python3
"""Tests for user-configurable work-authorization eligibility.

The engine encodes no country's rules. The candidate states their own facts
(authorized countries, citizenship/residency, countries needing sponsorship)
and chooses SKIP / REVIEW / IGNORE for each kind of posting restriction.
These tests verify that:
  A) the user's action is applied when the candidate's facts confirm the gap;
  B) SKIP is softened to REVIEW when the candidate's status is unknown;
  C) a candidate already authorized for the country is never blocked;
  D) IGNORE records the signal without affecting the gate;
  E) an ordinary posting with no authorization text is unaffected.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys


AUTOMATION_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = AUTOMATION_ROOT.parent / '15_Application_Engine'
sys.path.insert(0, str(AUTOMATION_ROOT))

from eligibility import classify_language_requirements, classify_work_authorization  # noqa: E402
from hard_filters.evaluate_hard_gates import evaluate_hard_gates  # noqa: E402


COUNTRY = 'Exampleland'


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def job(notes: str) -> dict:
    return {
        'Company': 'Synthetic Test',
        'Role_Title': 'Business Analyst',
        'Seniority': 'Analyst',
        'Country': COUNTRY,
        'Required_Experience_Years': 1,
        'Required_Experience_Requirement': {
            'status': 'EXPLICIT', 'minimum_years': 1, 'maximum_years': 2,
            'open_ended_minimum': False, 'approximate': False, 'source_text': '1-2 years',
        },
        'Job_Description_Clean': notes,
        'Job_Description_Raw': notes,
        'Work_Authorization_Notes': notes,
        'Mandatory_Education': [],
    }


def profile_with(base: dict, **facts) -> dict:
    profile = deepcopy(base)
    profile['location_constraints'] = dict(profile.get('location_constraints') or {}, work_authorization_countries=[])
    profile['work_authorization_facts'] = {
        'authorized_countries': [], 'citizen_or_resident_countries': [], 'requires_sponsorship_countries': [],
        **facts,
    }
    return profile


def strategy_with(**preferences) -> dict:
    return {'eligibility_preferences': preferences}


def evaluate(profile: dict, posting: dict, strategy: dict) -> dict:
    return evaluate_hard_gates(
        posting, profile, [],
        work_authorization=classify_work_authorization(posting, profile, strategy),
        language_assessments=classify_language_requirements(posting, profile, strategy),
        strategy=strategy,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--profile', default=str(ENGINE_ROOT / 'candidate_profile.json'))
    args = parser.parse_args()
    base = load_json(Path(args.profile))
    needs_sponsorship = profile_with(base, requires_sponsorship_countries=[COUNTRY])
    unknown_status = profile_with(base)
    authorized = profile_with(base, authorized_countries=[COUNTRY])
    citizen = profile_with(base, citizen_or_resident_countries=[COUNTRY])
    checks = []

    def check(test_id: str, condition: bool, evidence: object) -> None:
        checks.append({'test': test_id, 'status': 'PASS' if condition else 'FAIL', 'evidence': evidence})

    citizen_only = job('Applicants must be citizens or permanent residents only.')
    no_sponsor = job('The company is unable to provide visa sponsorship for this role.')

    gate = evaluate(needs_sponsorship, citizen_only, strategy_with(citizen_or_resident_only='SKIP'))
    check('A1_citizen_only_skip_fails_when_confirmed',
          gate['Hard_Gate_Status'] == 'FAIL'
          and gate['Work_Authorization_Assessment']['work_authorization_signal'] == 'CITIZEN_OR_RESIDENT_ONLY', gate)

    gate = evaluate(needs_sponsorship, citizen_only, strategy_with(citizen_or_resident_only='REVIEW'))
    check('A2_citizen_only_review_goes_to_review', gate['Hard_Gate_Status'] == 'MANUAL_REVIEW', gate)

    gate = evaluate(needs_sponsorship, no_sponsor, strategy_with(no_sponsorship='SKIP'))
    check('A3_no_sponsorship_skip_fails_when_confirmed',
          gate['Hard_Gate_Status'] == 'FAIL'
          and gate['Work_Authorization_Assessment']['work_authorization_signal'] == 'NO_SPONSORSHIP_AVAILABLE', gate)

    gate = evaluate(unknown_status, no_sponsor, strategy_with(no_sponsorship='SKIP'))
    check('B_skip_softened_to_review_when_status_unknown',
          gate['Hard_Gate_Status'] == 'MANUAL_REVIEW'
          and gate['Work_Authorization_Assessment']['hard_gate_effect'] == 'MANUAL_REVIEW', gate)

    gate = evaluate(authorized, no_sponsor, strategy_with(no_sponsorship='SKIP'))
    check('C1_authorized_candidate_not_blocked_by_no_sponsorship',
          gate['Work_Authorization_Assessment']['hard_gate_effect'] == 'NONE', gate)

    gate = evaluate(citizen, citizen_only, strategy_with(citizen_or_resident_only='SKIP'))
    check('C2_citizen_candidate_not_blocked_by_citizen_only',
          gate['Work_Authorization_Assessment']['hard_gate_effect'] == 'NONE', gate)

    gate = evaluate(needs_sponsorship, no_sponsor, strategy_with(no_sponsorship='IGNORE'))
    check('D_ignore_records_signal_without_effect',
          gate['Work_Authorization_Assessment']['work_authorization_signal'] == 'NO_SPONSORSHIP_AVAILABLE'
          and gate['Work_Authorization_Assessment']['hard_gate_effect'] == 'NONE', gate)

    gate = evaluate(authorized, job(''), strategy_with())
    check('E_ordinary_posting_unaffected',
          gate['Work_Authorization_Assessment']['work_authorization_signal'] == 'NOT_STATED'
          and gate['Work_Authorization_Assessment']['hard_gate_effect'] == 'NONE', gate)

    failed = [item for item in checks if item['status'] == 'FAIL']
    result = {
        'stage': 'user-configurable work-authorization tests',
        'tests_passed': len(checks) - len(failed),
        'tests_failed': len(failed),
        'overall_status': 'PASS' if not failed else 'FAIL',
        'checks': checks,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'checks'}, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
