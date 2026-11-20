#!/usr/bin/env python3
"""Targeted tests for the Stage 5B application-routing modules (2026-09-03).

Covers Step 11 items 1-15 of the Stage 5B task instruction. All connector
interaction is injected/fake -- these tests never touch the network.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


AUTOMATION_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AUTOMATION_ROOT))

from job_discovery.base_connector import SourceAccessError  # noqa: E402
from routing.build_routing_record import build_routing_record  # noqa: E402
from routing.verify_vacancy import verify_vacancy  # noqa: E402


def job(job_id='JOB-TEST-0001', company='Synthetic Co', role_title='Business Analyst') -> dict:
    return {'Job_ID': job_id, 'Company': company, 'Role_Title': role_title, 'Source_URL': None}


def provenance(*, primary_source=None, application_urls=None, source_urls=None,
                source_job_id='abc123', requisition_id=None, source_api_url=None,
                extra_source_records=None) -> dict:
    records = [{
        'source_job_id': source_job_id,
        'requisition_id': requisition_id,
        'source_api_url': source_api_url,
    }]
    if extra_source_records:
        records.extend(extra_source_records)
    return {
        'primary_source': primary_source,
        'application_urls': application_urls if application_urls is not None else ['https://example.test/apply'],
        'source_urls': source_urls if source_urls is not None else ['https://example.test/posting'],
        'source_records': records,
    }


# --- Fake connectors for verify_vacancy() injection -------------------------

class FakeConnector:
    """Fake connector matching the real BaseJobConnector-derived interface
    (discover() -> list[dict], extract_source_fields(dict) -> dict) without
    any network access."""

    postings: list[dict] = []

    def __init__(self, board, company, timeout=20):
        self.board = board
        self.company = company

    def discover(self) -> list[dict]:
        return self.postings

    def extract_source_fields(self, source_job: dict) -> dict:
        return {
            'source_job_id': source_job.get('id'),
            'requisition_id': source_job.get('requisition_id'),
            'job_title': source_job.get('title'),
            'company': source_job.get('company', self.company),
        }


def make_fake_connector(postings: list[dict]):
    return type('FakeConnectorInstance', (FakeConnector,), {'postings': postings})


class FailingConnector:
    def __init__(self, board, company, timeout=20):
        pass

    def discover(self) -> list[dict]:
        raise SourceAccessError('SOURCE_ACCESS_LIMITED', 'simulated network failure')

    def extract_source_fields(self, source_job: dict) -> dict:  # pragma: no cover - unreachable
        raise AssertionError('extract_source_fields should not be called after a discover() failure')


def fixed_clock(iso_value='2026-09-03T20:00:00+00:00'):
    return lambda: _FixedDatetime(iso_value)


class _FixedDatetime:
    def __init__(self, iso_value):
        self._iso_value = iso_value

    def isoformat(self):
        return self._iso_value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    checks: list[dict] = []

    def check(test_id: str, condition: bool, evidence: object) -> None:
        checks.append({'test': test_id, 'status': 'PASS' if condition else 'FAIL', 'evidence': evidence})

    # 1. Lever provider detection
    r = build_routing_record(job(), provenance(primary_source='Lever Public API'))
    check('01_lever_provider_detection', r['ats_provider'] == 'LEVER', r['ats_provider'])

    # 2. Greenhouse: boards.greenhouse.io
    r = build_routing_record(
        job(), provenance(primary_source=None, application_urls=['https://boards.greenhouse.io/acme/jobs/123']),
    )
    check('02_greenhouse_boards_domain', r['ats_provider'] == 'GREENHOUSE', r['ats_provider'])

    # 3. Greenhouse: job-boards.greenhouse.io
    r = build_routing_record(
        job(), provenance(primary_source=None, application_urls=['https://job-boards.greenhouse.io/acme/jobs/123']),
    )
    check('03_greenhouse_job_boards_domain', r['ats_provider'] == 'GREENHOUSE', r['ats_provider'])

    # 4. Ashby provider detection
    r = build_routing_record(job(), provenance(primary_source='Ashby Public API'))
    check('04_ashby_provider_detection', r['ats_provider'] == 'ASHBY', r['ats_provider'])

    # 5. UNKNOWN provider
    r = build_routing_record(
        job(), provenance(primary_source='Some Other ATS', application_urls=['https://careers.example.com/job/1']),
    )
    check('05_unknown_provider', r['ats_provider'] == 'UNKNOWN', r['ats_provider'])

    # 6. one application URL
    r = build_routing_record(job(), provenance(application_urls=['https://example.test/apply']))
    check(
        '06_one_application_url',
        r['application_url'] == 'https://example.test/apply' and r['routing_status'] == 'ROUTED',
        r,
    )

    # 7. zero application URLs -> VACANCY_URL_MISSING
    r = build_routing_record(job(), provenance(application_urls=[]))
    check(
        '07_zero_application_urls',
        r['application_url'] is None and r['routing_status'] == 'VACANCY_URL_MISSING',
        r,
    )

    # 8. multiple equivalent application URLs -> deterministic selection
    r1 = build_routing_record(
        job(), provenance(application_urls=['https://example.test/apply', 'https://example.test/apply/']),
    )
    r2 = build_routing_record(
        job(), provenance(application_urls=['https://example.test/apply', 'https://example.test/apply/']),
    )
    check(
        '08_multiple_equivalent_urls_deterministic',
        r1['application_url'] == 'https://example.test/apply' and r1['routing_status'] == 'ROUTED' and r1 == r2,
        r1,
    )

    # 9. multiple materially different application URLs -> NEEDS_HUMAN_REVIEW
    r = build_routing_record(
        job(), provenance(application_urls=['https://example.test/apply', 'https://example.test/other-role/apply']),
    )
    check(
        '09_multiple_different_urls_needs_review',
        r['application_url'] is None and r['routing_status'] == 'NEEDS_HUMAN_REVIEW',
        r,
    )

    # 10. pure-build determinism (also: no network, no clock -- verified by
    # the fact this needs no injected clock/connector at all)
    j, p = job(), provenance(primary_source='Lever Public API', requisition_id='REQ-1')
    ra = build_routing_record(j, p)
    rb = build_routing_record(j, p)
    check(
        '10_pure_build_determinism',
        ra == rb and json.dumps(ra, sort_keys=True) == json.dumps(rb, sort_keys=True)
        and ra['verification_timestamp'] is None,
        {'equal': ra == rb},
    )

    # 11. source_job_id still present -> VERIFIED_ACTIVE / ROUTED
    j = job(role_title='Business Analyst', company='Synthetic Co')
    p = provenance(
        primary_source='Lever Public API',
        source_job_id='job-1', requisition_id=None,
        source_api_url='https://api.lever.co/v0/postings/synthetic-co?mode=json',
    )
    record = build_routing_record(j, p)
    connector_types = {'lever': make_fake_connector([{'id': 'job-1', 'title': 'Business Analyst'}])}
    result = verify_vacancy(j, p, record, connector_types=connector_types, now=fixed_clock())
    check(
        '11_source_job_id_present_verified_active',
        result['verification_status'] == 'VERIFIED_ACTIVE' and result['routing_status'] == 'ROUTED'
        and result['verification_timestamp'] == '2026-09-03T20:00:00+00:00'
        and result['verification_method'] == 'SOURCE_API_REPOLL',
        result,
    )

    # 12. source_job_id absent after successful fresh discovery -> VERIFIED_REMOVED_OR_CLOSED
    connector_types = {'lever': make_fake_connector([{'id': 'some-other-job', 'title': 'Unrelated Role'}])}
    result = verify_vacancy(j, p, record, connector_types=connector_types, now=fixed_clock())
    check(
        '12_source_job_id_absent_removed_or_closed',
        result['verification_status'] == 'VERIFIED_REMOVED_OR_CLOSED' and result['routing_status'] == 'VACANCY_NOT_FOUND',
        result,
    )

    # 13. requisition_id changed -> VACANCY_MISMATCH_SUSPECTED
    j_gh = job(role_title='Financial Analyst', company='Acme')
    p_gh = provenance(
        primary_source='Greenhouse Public API',
        source_job_id='gh-1', requisition_id='REQ-OLD',
        source_api_url='https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true',
    )
    record_gh = build_routing_record(j_gh, p_gh)
    connector_types = {
        'greenhouse': make_fake_connector([
            {'id': 'gh-1', 'title': 'Financial Analyst', 'requisition_id': 'REQ-NEW', 'company': 'Acme'},
        ]),
    }
    result = verify_vacancy(j_gh, p_gh, record_gh, connector_types=connector_types, now=fixed_clock())
    check(
        '13_requisition_id_changed_mismatch_suspected',
        result['routing_status'] == 'VACANCY_MISMATCH_SUSPECTED' and result['verification_status'] == 'VERIFIED_ACTIVE',
        result,
    )

    # 14. same source_job_id but materially changed title/company -> NEEDS_HUMAN_REVIEW
    connector_types = {
        'greenhouse': make_fake_connector([
            {'id': 'gh-1', 'title': 'Completely Different Role Title', 'requisition_id': 'REQ-OLD', 'company': 'Acme'},
        ]),
    }
    result = verify_vacancy(j_gh, p_gh, record_gh, connector_types=connector_types, now=fixed_clock())
    check(
        '14_title_changed_needs_human_review',
        result['routing_status'] == 'NEEDS_HUMAN_REVIEW' and result['verification_status'] == 'VERIFIED_ACTIVE',
        result,
    )

    # 15. connector/source-access failure -> VERIFICATION_FAILED, NOT VACANCY_NOT_FOUND
    connector_types = {'lever': FailingConnector}
    result = verify_vacancy(j, p, record, connector_types=connector_types, now=fixed_clock())
    check(
        '15_connector_failure_verification_failed_not_vacancy_not_found',
        result['verification_status'] == 'VERIFICATION_FAILED'
        and result['routing_status'] == 'NEEDS_HUMAN_REVIEW'
        and result['routing_status'] != 'VACANCY_NOT_FOUND',
        result,
    )

    # --- extra regression guards, beyond the required 15 -------------------

    # Requisition-id absent both sides (Lever/Ashby shape) must not spuriously
    # trigger the mismatch-suspected path.
    connector_types = {'lever': make_fake_connector([{'id': 'job-1', 'title': 'Business Analyst'}])}
    result = verify_vacancy(j, p, record, connector_types=connector_types, now=fixed_clock())
    check(
        '16_no_requisition_id_either_side_not_mismatch',
        result['routing_status'] == 'ROUTED',
        result,
    )

    # Multiple distinct source_job_id values in provenance -> NEEDS_HUMAN_REVIEW at build time.
    p_anomaly = provenance(
        primary_source='Lever Public API', source_job_id='job-A',
        extra_source_records=[{'source_job_id': 'job-B', 'requisition_id': None, 'source_api_url': None}],
    )
    r = build_routing_record(job(), p_anomaly)
    check(
        '17_ambiguous_source_job_id_needs_human_review',
        r['routing_status'] == 'NEEDS_HUMAN_REVIEW' and 'anomaly' in r['routing_evidence'],
        r,
    )

    # Unsupported/UNKNOWN ats_provider is never silently verified as active.
    j_unknown = job()
    p_unknown = provenance(primary_source='SomeOtherATS Public API')
    record_unknown = build_routing_record(j_unknown, p_unknown)
    result = verify_vacancy(j_unknown, p_unknown, record_unknown, connector_types={}, now=fixed_clock())
    check(
        '18_unknown_provider_verification_failed_not_active',
        result['verification_status'] == 'VERIFICATION_FAILED' and result['routing_status'] == 'NEEDS_HUMAN_REVIEW',
        result,
    )

    failed = [item for item in checks if item['status'] == 'FAIL']
    result_report = {
        'stage': 'Stage 5B application-routing targeted tests',
        'tests_passed': len(checks) - len(failed),
        'tests_failed': len(failed),
        'overall_status': 'PASS' if not failed else 'FAIL',
        'checks': checks,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result_report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(result_report, indent=2, ensure_ascii=False))
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
