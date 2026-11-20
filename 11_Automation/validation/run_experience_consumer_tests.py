#!/usr/bin/env python3
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys


AUTOMATION_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AUTOMATION_ROOT))

from hard_filters.evaluate_hard_gates import evaluate_hard_gates  # noqa: E402
from hard_filters.experience_semantics import (  # noqa: E402
    classify_early_career,
    evaluate_experience_gate,
    interpret_experience_requirement,
)
from job_discovery.normalize_source import _extract_experience_requirement  # noqa: E402


def metadata(
    minimum: float | None,
    maximum: float | None = None,
    *,
    open_minimum: bool = False,
    approximate: bool = False,
    source_text: str | None = None,
) -> dict:
    return {
        'status': 'UNKNOWN' if minimum is None else 'EXPLICIT',
        'minimum_years': minimum,
        'maximum_years': maximum,
        'open_ended_minimum': open_minimum,
        'approximate': approximate,
        'source_text': source_text,
    }


def job(requirement: dict | None, scalar: float | None, *, jd: str = '') -> dict:
    return {
        'Company': 'Synthetic Test',
        'Role_Title': 'Business Analyst',
        'Seniority': 'Analyst',
        'Country': 'Singapore',
        'Required_Experience_Years': scalar,
        'Required_Experience_Requirement': requirement,
        'Job_Description_Clean': jd,
        'Job_Description_Raw': jd,
        'Mandatory_Education': [],
    }


PROFILE = {
    'location_constraints': {'work_authorization_countries': ['Singapore']},
    'work_authorization_facts': {},
}
WORK_AUTHORIZATION = {
    'work_authorization_signal': 'NOT_STATED',
    'hard_gate_effect': 'NONE',
    'policy_interpretation': 'No explicit restriction.',
    'human_review_required': False,
}


def hard_gate(value: dict) -> dict:
    return evaluate_hard_gates(
        value,
        PROFILE,
        [],
        work_authorization=WORK_AUTHORIZATION,
        language_assessments=[],
        employment_policy=None,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    checks = []

    def check(test_id: str, condition: bool, evidence: object) -> None:
        checks.append({'test': test_id, 'status': 'PASS' if condition else 'FAIL', 'evidence': evidence})

    open_six = job(metadata(6, open_minimum=True, source_text='6+ years'), 1)
    open_six_gate = hard_gate(open_six)
    open_six_semantic = open_six_gate['Experience_Interpretation']
    check(
        'A_open_minimum_above_threshold',
        open_six_semantic['Semantic_Type'] == 'OPEN_MINIMUM'
        and open_six_semantic['Source'] == 'CANONICAL_METADATA'
        and open_six_gate['Hard_Gate_Status'] == 'FAIL'
        and '6+ years' in ' '.join(open_six_gate['Hard_Gate_Reasons']),
        {'semantic': open_six_semantic, 'gate': open_six_gate},
    )

    high_range = job(metadata(10, 12, source_text='10–12 years'), 99)
    high_range_gate = hard_gate(high_range)
    high_range_reason = ' '.join(high_range_gate['Hard_Gate_Reasons'])
    check(
        'B_bounded_high_range',
        high_range_gate['Experience_Interpretation']['Semantic_Type'] == 'BOUNDED_RANGE'
        and high_range_gate['Hard_Gate_Status'] == 'FAIL'
        and '10–12 years' in high_range_reason
        and '10+ years' not in high_range_reason,
        {'semantic': high_range_gate['Experience_Interpretation'], 'gate': high_range_gate},
    )

    low_range = job(metadata(1, 2, source_text='1–2 years'), 99)
    low_range_gate = hard_gate(low_range)
    low_range_early = classify_early_career(low_range)
    check(
        'C_low_bounded_range',
        low_range_gate['Experience_Interpretation']['Semantic_Type'] == 'BOUNDED_RANGE'
        and low_range_gate['Hard_Gate_Status'] == 'PASS'
        and low_range_early['Classification'] == 'TARGET'
        and '1–2 years' in low_range_early['Reason']
        and '1+' not in low_range_early['Reason'],
        {'gate': low_range_gate, 'early_career': low_range_early},
    )

    approximate_five = job(metadata(5, approximate=True, source_text='approximately 5 years'), 5)
    approximate_gate = hard_gate(approximate_five)
    approximate_reason = ' '.join(approximate_gate['Hard_Gate_Reasons'])
    check(
        'D_approximate_five',
        approximate_gate['Experience_Interpretation']['Semantic_Type'] == 'APPROXIMATE'
        and approximate_gate['Hard_Gate_Status'] == 'MANUAL_REVIEW'
        and 'Approximately 5 years' in approximate_reason
        and '5+ years' not in approximate_reason,
        {'semantic': approximate_gate['Experience_Interpretation'], 'gate': approximate_gate},
    )

    open_five = job(metadata(5, open_minimum=True, source_text='5+ years'), 5)
    open_five_gate = hard_gate(open_five)
    check(
        'E_explicit_five_plus',
        open_five_gate['Experience_Interpretation']['Semantic_Type'] == 'OPEN_MINIMUM'
        and open_five_gate['Hard_Gate_Status'] == 'FAIL'
        and '5+ years' in ' '.join(open_five_gate['Hard_Gate_Reasons']),
        {'semantic': open_five_gate['Experience_Interpretation'], 'gate': open_five_gate},
    )

    check(
        'F_metadata_overrides_scalar',
        approximate_gate['Experience_Interpretation']['Source'] == 'CANONICAL_METADATA'
        and approximate_gate['Experience_Interpretation']['Semantic_Type'] == 'APPROXIMATE'
        and approximate_gate['Hard_Gate_Status'] == 'MANUAL_REVIEW',
        {'scalar': 5, 'semantic': approximate_gate['Experience_Interpretation']},
    )

    legacy = job(None, 5)
    legacy_gate = hard_gate(legacy)
    check(
        'G_legacy_scalar_fallback',
        legacy_gate['Experience_Interpretation']['Semantic_Type'] == 'LEGACY_SCALAR'
        and legacy_gate['Experience_Interpretation']['Source'] == 'LEGACY_SCALAR_FALLBACK'
        and legacy_gate['Hard_Gate_Status'] == 'FAIL',
        {'semantic': legacy_gate['Experience_Interpretation'], 'gate': legacy_gate},
    )

    unknown = job(metadata(None), 99)
    unknown_gate = hard_gate(unknown)
    check(
        'H_unknown_is_authoritative',
        unknown_gate['Experience_Interpretation']['Semantic_Type'] == 'UNKNOWN'
        and unknown_gate['Experience_Interpretation']['Source'] == 'CANONICAL_METADATA'
        and unknown_gate['Hard_Gate_Status'] == 'MANUAL_REVIEW',
        {'scalar': 99, 'semantic': unknown_gate['Experience_Interpretation'], 'gate': unknown_gate},
    )

    company_history_text = 'Our company has 30 years of experience serving clients, but the role states no candidate experience requirement.'
    extracted = _extract_experience_requirement(company_history_text)
    history_job = job(extracted, extracted['minimum_years'], jd=company_history_text)
    history_gate = hard_gate(history_job)
    check(
        'I_company_history_negative_control',
        extracted['status'] == 'UNKNOWN'
        and history_gate['Experience_Interpretation']['Semantic_Type'] == 'UNKNOWN'
        and history_gate['Hard_Gate_Status'] == 'MANUAL_REVIEW',
        {'extracted': extracted, 'semantic': history_gate['Experience_Interpretation'], 'gate': history_gate},
    )

    inputs = [open_six, high_range, low_range, approximate_five, open_five, legacy, unknown, history_job]
    first = [
        {
            'semantic': interpret_experience_requirement(item),
            'gate': hard_gate(item),
            'early_career': classify_early_career(item),
        }
        for item in inputs
    ]
    second = [
        {
            'semantic': interpret_experience_requirement(deepcopy(item)),
            'gate': hard_gate(deepcopy(item)),
            'early_career': classify_early_career(deepcopy(item)),
        }
        for item in inputs
    ]
    check('J_determinism', first == second, {'equal': first == second})

    failed = [item for item in checks if item['status'] == 'FAIL']
    result = {
        'stage': 'Downstream Experience Consumer targeted tests',
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
