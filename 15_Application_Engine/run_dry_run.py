#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ENGINE_ROOT = Path(__file__).resolve().parent
CAREER_OS_ROOT = ENGINE_ROOT.parent
AUTOMATION_ROOT = CAREER_OS_ROOT / '11_Automation'
sys.path.insert(0, str(AUTOMATION_ROOT))

from common import dump_json, load_json  # noqa: E402
from fit_scoring.score_job import score_job  # noqa: E402
from gap_analysis.classify_gaps import analyze_gaps  # noqa: E402
from hard_filters.evaluate_hard_gates import evaluate_hard_gates  # noqa: E402
from job_normalization.normalize_job import normalize_job  # noqa: E402
from eligibility import classify_language_requirements, classify_work_authorization  # noqa: E402
from qa.untrusted_input import detect_untrusted_instructions  # noqa: E402
from resume_router.route_resume import route_resume  # noqa: E402


def evaluate_job(
    raw_job: dict,
    profile: dict,
    sequence: int = 1,
    strategy: dict | None = None,
) -> dict:
    job = normalize_job(raw_job, sequence=sequence)
    route = route_resume(job)
    job['Career_Direction'] = route['Primary_Route']
    job['Primary_Route'] = route['Primary_Route']
    job['Secondary_Route'] = route['Secondary_Route']
    job['Routing_Confidence'] = route['Routing_Confidence']
    job['Recommended_Resume'] = route['Recommended_Resume']
    job['Primary_Resume'] = route['Primary_Resume']
    job['Primary_Reason'] = route['Primary_Reason']
    job['Optional_Secondary_Resume'] = route['Optional_Secondary_Resume']
    job['Base_Selection_Scores'] = route['Base_Scores']
    job['Secondary_Reason'] = route['Secondary_Reason']
    job['Secondary_Allowed'] = route['Secondary_Allowed']
    job['Routing_Human_Review_Required'] = route['Human_Review_Required']
    work_authorization = classify_work_authorization(job, profile, strategy)
    language_assessments = classify_language_requirements(job, profile, strategy)
    gaps = analyze_gaps(job, profile, work_authorization, language_assessments)
    gate = evaluate_hard_gates(
        job, profile, gaps,
        work_authorization=work_authorization,
        language_assessments=language_assessments,
        strategy=strategy,
    )
    job['Hard_Gate_Status'] = gate['Hard_Gate_Status']
    job['Hard_Gate_Reasons'] = gate['Hard_Gate_Reasons']
    job['Work_Authorization_Assessment'] = work_authorization
    job['Language_Assessments'] = language_assessments
    job['Location_Assessment'] = gate['Location_Assessment']
    job['Employment_Type_Assessment'] = gate['Employment_Type_Assessment']
    job['Circuit_Breaker'] = gate['Circuit_Breaker']
    job['Prompt_Injection_Signals'] = detect_untrusted_instructions(job)
    scoring = score_job(job, profile, route, gate, gaps, strategy)
    for key in ['Fit_Score', 'Fit_Score_Breakdown', 'Assessment_Confidence', 'Decision', 'Status', 'Top_Matches', 'Gaps', 'Gap_Count']:
        job[key] = scoring[key]
    job['Fit_Explanation'] = scoring['Explanation']
    return job


def main() -> None:
    parser = argparse.ArgumentParser(description='Score a manually supplied canonical job JSON without scraping or applying.')
    parser.add_argument('--input', required=True, help='Path to one canonical job object or an array of job objects.')
    parser.add_argument('--output', required=True, help='Path for the scored JSON result.')
    parser.add_argument('--profile', default=str(ENGINE_ROOT / 'candidate_profile.json'))
    parser.add_argument('--strategy', default=str(ENGINE_ROOT / 'candidate_strategy.json'))
    args = parser.parse_args()
    profile = load_json(Path(args.profile))
    strategy_path = Path(args.strategy)
    strategy = load_json(strategy_path) if strategy_path.exists() else None
    raw = load_json(Path(args.input))
    if isinstance(raw, list):
        result = [evaluate_job(item, profile, index + 1, strategy) for index, item in enumerate(raw)]
    else:
        result = evaluate_job(raw, profile, 1, strategy)
    dump_json(Path(args.output), result)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
