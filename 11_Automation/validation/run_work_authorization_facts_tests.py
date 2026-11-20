#!/usr/bin/env python3
"""Targeted tests for work-authorization facts in the hard-gate layer.

Uses the candidate profile passed via --profile (the repository ships a
synthetic profile whose candidate is not a Singapore citizen/PR and requires
employer sponsorship) and verifies that:
  A) an explicit "Singapore Citizens/PR only" posting resolves to
     Hard_Gate_Status == FAIL.
  B) an explicit "no sponsorship available" Singapore posting resolves to
     Hard_Gate_Status == MANUAL_REVIEW rather than a silent pass. It is
     intentionally MANUAL_REVIEW, not an automatic FAIL, per the engine's
     ambiguity policy; this test locks that choice in so any change is a
     deliberate diff.
  C) an ordinary posting with no work-authorization text is unaffected
     (hard_gate_effect stays NONE).
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
from policy.singapore.language_classifier import classify_language_requirements  # noqa: E402
from policy.singapore.work_authorization import classify_work_authorization  # noqa: E402


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def job(work_authorization_notes: str) -> dict:
    return {
        'Company': 'Synthetic Test',
        'Role_Title': 'Business Analyst',
        'Seniority': 'Analyst',
        'Country': 'Singapore',
        'Required_Experience_Years': 1,
        'Required_Experience_Requirement': {
            'status': 'EXPLICIT', 'minimum_years': 1, 'maximum_years': 2,
            'open_ended_minimum': False, 'approximate': False, 'source_text': '1-2 years',
        },
        'Job_Description_Clean': work_authorization_notes,
        'Job_Description_Raw': work_authorization_notes,
        'Work_Authorization_Notes': work_authorization_notes,
        'Mandatory_Education': [],
    }


def evaluate(profile: dict, posting: dict) -> dict:
    work_authorization = classify_work_authorization(posting, profile)
    language_assessments = classify_language_requirements(posting, profile)
    return evaluate_hard_gates(
        posting, profile, [],
        work_authorization=work_authorization,
        language_assessments=language_assessments,
        employment_policy=None,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--profile', default=str(ENGINE_ROOT / 'candidate_profile.json'))
    args = parser.parse_args()
    profile = load_json(Path(args.profile))
    checks = []

    def check(test_id: str, condition: bool, evidence: object) -> None:
        checks.append({'test': test_id, 'status': 'PASS' if condition else 'FAIL', 'evidence': evidence})

    citizen_pr_only = job('Applicants must be Singapore Citizens or Singapore PR only.')
    gate_a = evaluate(profile, citizen_pr_only)
    check(
        'A_citizen_pr_only_hard_fails',
        gate_a['Hard_Gate_Status'] == 'FAIL'
        and gate_a['Work_Authorization_Assessment']['work_authorization_signal'] == 'EXPLICIT_LOCAL_ONLY'
        and gate_a['Work_Authorization_Assessment']['hard_gate_effect'] == 'CRITICAL_HARD_REQUIREMENT_MISSING',
        gate_a,
    )

    no_sponsorship = job('The company is unable to provide visa sponsorship for this role.')
    gate_b = evaluate(profile, no_sponsorship)
    check(
        'B_no_sponsorship_manual_review_not_silent_pass',
        gate_b['Hard_Gate_Status'] == 'MANUAL_REVIEW'
        and gate_b['Work_Authorization_Assessment']['work_authorization_signal'] == 'NO_SPONSORSHIP_AVAILABLE'
        and gate_b['Work_Authorization_Assessment']['hard_gate_effect'] == 'MANUAL_REVIEW',
        gate_b,
    )

    ordinary = job('')
    gate_c = evaluate(profile, ordinary)
    check(
        'C_ordinary_posting_unaffected',
        gate_c['Work_Authorization_Assessment']['work_authorization_signal'] == 'NOT_STATED'
        and gate_c['Work_Authorization_Assessment']['hard_gate_effect'] == 'NONE',
        gate_c,
    )

    failed = [item for item in checks if item['status'] == 'FAIL']
    result = {
        'stage': 'work_authorization_facts patch targeted tests',
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
