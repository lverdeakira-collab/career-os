from __future__ import annotations

import json
from pathlib import Path
import re

from .deduplication import compact, jd_fingerprint


def load_seen(seen_dir: Path) -> list[dict]:
    if not seen_dir.exists():
        return []
    records = []
    for path in sorted(seen_dir.glob('JOB-*.seen.json')):
        records.append(json.loads(path.read_text(encoding='utf-8')))
    return records


def source_keys(group: list[dict]) -> list[str]:
    return sorted({f"{record['source_connector']}:{record['source_job_id']}" for record in group})


def vacancy_key(record: dict) -> str:
    return '|'.join([compact(record.get('company')), compact(record.get('job_title')), compact(record.get('location_raw')), jd_fingerprint(record)])


def existing_job_id(group: list[dict], seen_records: list[dict]) -> str | None:
    keys = set(source_keys(group))
    requisitions = {str(record.get('requisition_id')) for record in group if record.get('requisition_id')}
    fingerprints = {vacancy_key(record) for record in group}
    for seen in seen_records:
        if keys & set(seen.get('source_identity_keys') or []):
            return seen['job_id']
        if requisitions & set(seen.get('requisition_ids') or []) and compact(group[0].get('company')) == compact(seen.get('company')):
            return seen['job_id']
        if fingerprints & set(seen.get('vacancy_fingerprints') or []):
            return seen['job_id']
    return None


def next_sequence(seen_records: list[dict], existing_job_ids: list[str]) -> int:
    values = []
    for value in [item.get('job_id') for item in seen_records] + existing_job_ids:
        match = re.search(r'-(\d{4})$', value or '')
        if match:
            values.append(int(match.group(1)))
    return max(values, default=0) + 1


def build_seen_record(job_id: str, group: list[dict], run_time: str, previous: dict | None = None) -> dict:
    urls = sorted({url for record in group for url in [record.get('source_url'), record.get('application_link_raw'), record.get('source_api_url')] if url})
    source_ids = source_keys(group)
    requisitions = sorted({str(record['requisition_id']) for record in group if record.get('requisition_id')})
    fingerprints = sorted({vacancy_key(record) for record in group})
    prior_count = int((previous or {}).get('times_seen') or 0)
    return {
        'schema_version': '0.1',
        'job_id': job_id,
        'company': group[0].get('company'),
        'role_title': group[0].get('job_title'),
        'location': group[0].get('location_raw'),
        'first_seen_at': (previous or {}).get('first_seen_at') or run_time,
        'last_seen_at': run_time,
        'times_seen': prior_count + len(group),
        'active_status': 'ACTIVE',
        'latest_source_urls': urls,
        'latest_posting_status': 'ACTIVE',
        'source_identity_keys': sorted(set((previous or {}).get('source_identity_keys') or []) | set(source_ids)),
        'requisition_ids': sorted(set((previous or {}).get('requisition_ids') or []) | set(requisitions)),
        'vacancy_fingerprints': sorted(set((previous or {}).get('vacancy_fingerprints') or []) | set(fingerprints)),
        'last_run_id': group[0].get('run_id'),
    }
