#!/usr/bin/env python3
"""Stage 5B driver: build routing records for all Stage 4 jobs, and
optionally run live vacancy verification for a named subset (pilot).

Reads ONLY from 08_Job_Search/Normalized_Jobs/*.json + *.provenance.json.
Writes ONLY to 15_Application_Engine/routing_records/*.routing.json.
Never writes into 08_Job_Search/ (downstream-only, per the Stage 5B
architecture boundary).
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


AUTOMATION_ROOT = Path(__file__).resolve().parents[1]
CAREER_ROOT = AUTOMATION_ROOT.parent
ENGINE_ROOT = CAREER_ROOT / '15_Application_Engine'
sys.path.insert(0, str(AUTOMATION_ROOT))

from common import dump_json, load_json  # noqa: E402
from job_discovery import CONNECTOR_TYPES  # noqa: E402
from routing.build_routing_record import build_routing_record  # noqa: E402
from routing.verify_vacancy import verify_vacancy  # noqa: E402


NORMALIZED_ROOT = CAREER_ROOT / '08_Job_Search/Normalized_Jobs'
ROUTING_ROOT = ENGINE_ROOT / 'routing_records'


def load_all_jobs() -> list[tuple[dict, dict]]:
    pairs = []
    for job_path in sorted(NORMALIZED_ROOT.glob('JOB-*.json')):
        if job_path.name.endswith('.provenance.json'):
            continue
        provenance_path = job_path.parent / (job_path.stem + '.provenance.json')
        job = load_json(job_path)
        provenance = load_json(provenance_path)
        pairs.append((job, provenance))
    return pairs


def build_static(pairs: list[tuple[dict, dict]]) -> dict[str, dict]:
    records = {}
    for job, provenance in pairs:
        record = build_routing_record(job, provenance)
        records[record['Job_ID']] = record
    return records


def write_records(records: dict[str, dict]) -> None:
    ROUTING_ROOT.mkdir(parents=True, exist_ok=True)
    for job_id, record in records.items():
        dump_json(ROUTING_ROOT / f'{job_id}.routing.json', record)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Write routing_records/*.routing.json (static build only).')
    parser.add_argument(
        '--verify-pilot', nargs='*', default=None,
        help='Job_IDs to live-verify (network access) and persist verification results for.',
    )
    args = parser.parse_args()

    pairs = load_all_jobs()
    by_job_id = {job['Job_ID']: (job, provenance) for job, provenance in pairs}
    records = build_static(pairs)

    if args.write:
        write_records(records)

    if args.verify_pilot is not None:
        ROUTING_ROOT.mkdir(parents=True, exist_ok=True)
        pilot_results = {}
        for job_id in args.verify_pilot:
            job, provenance = by_job_id[job_id]
            record = records[job_id]
            update = verify_vacancy(job, provenance, record, connector_types=CONNECTOR_TYPES)
            record.update(update)
            dump_json(ROUTING_ROOT / f'{job_id}.routing.json', record)
            pilot_results[job_id] = record
        dump_json(Path('/tmp/s5b/pilot_verification_results.json'), pilot_results)

    print(f'{len(records)} routing records built.')


if __name__ == '__main__':
    main()
