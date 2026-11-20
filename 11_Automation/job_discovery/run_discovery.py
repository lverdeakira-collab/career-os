#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from zoneinfo import ZoneInfo


MODULE_ROOT = Path(__file__).resolve().parent
AUTOMATION_BUILD_ROOT = MODULE_ROOT.parent
sys.path.insert(0, str(AUTOMATION_BUILD_ROOT))

from job_discovery import CONNECTOR_TYPES  # noqa: E402
from job_discovery.base_connector import SourceAccessError  # noqa: E402
from job_discovery.deduplication import group_records  # noqa: E402
from job_discovery.normalize_source import build_stage3_input  # noqa: E402
from job_discovery.seen_memory import build_seen_record, existing_job_id, load_seen, next_sequence  # noqa: E402


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def dump_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load_stage3(career_os_root: Path):
    automation_root = career_os_root / '11_Automation'
    engine_root = career_os_root / '15_Application_Engine'
    sys.path.insert(0, str(automation_root))
    sys.path.insert(0, str(engine_root))
    from job_normalization.normalize_job import make_job_id, normalize_role_title
    from run_dry_run import evaluate_job
    return make_job_id, normalize_role_title, evaluate_job


def existing_ids(job_index_path: Path) -> list[str]:
    if not job_index_path.exists():
        return []
    with job_index_path.open(newline='', encoding='utf-8') as handle:
        return [row.get('Job_ID') for row in csv.DictReader(handle) if row.get('Job_ID')]


def raw_filename(record: dict) -> str:
    board = str((record.get('source_metadata') or {}).get('board') or 'board').replace('/', '_')
    replay = '-replay' if record.get('validation_replay') else ''
    return f"{record['source_connector']}-{board}-{record['source_job_id']}{replay}.raw.json"


def main() -> None:
    parser = argparse.ArgumentParser(description='Controlled public-source discovery; no login, tailoring, or application submission.')
    parser.add_argument('--career-os-root', required=True)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--config', default=str(MODULE_ROOT / 'discovery_sources.json'))
    parser.add_argument('--run-id')
    args = parser.parse_args()

    career_root = Path(args.career_os_root)
    output_root = Path(args.output_root)
    config = load_json(Path(args.config))
    timezone_name = config.get('timezone') or 'UTC'
    now = datetime.now(ZoneInfo(timezone_name))
    run_id = args.run_id or now.strftime('DISCOVERY-%Y%m%d-%H%M%S')
    started_at = now.isoformat(timespec='seconds')
    discovered_date = now.date().isoformat()
    run_dir = output_root / '08_Job_Search/Discovery_Runs' / run_id
    raw_dir = output_root / '08_Job_Search/Raw_Jobs' / run_id
    normalized_dir = output_root / '08_Job_Search/Normalized_Jobs'
    seen_dir = output_root / '08_Job_Search/Seen_Jobs'
    dedup_dir = output_root / '08_Job_Search/Deduplication_Logs'
    for directory in [run_dir, raw_dir, normalized_dir, seen_dir, dedup_dir, output_root / '08_Job_Search/Shortlisted', output_root / '08_Job_Search/Rejected']:
        directory.mkdir(parents=True, exist_ok=True)

    make_job_id, normalize_role_title, evaluate_job = load_stage3(career_root)
    candidate_profile_path = career_root / '15_Application_Engine/candidate_profile.json'
    profile = load_json(candidate_profile_path)
    profile_bytes = candidate_profile_path.read_bytes()

    raw_records: list[dict] = []
    source_attempts = []
    warnings, errors = [], []
    connector_types_succeeded = set()

    for source in config['sources']:
        connector_type = source['connector']
        connector = CONNECTOR_TYPES[connector_type](source['board'], source['company'])
        attempt = {
            'connector': connector_type,
            'board': source['board'],
            'company': source['company'],
            'url': connector.discovery_url,
            'status': None,
            'jobs_available': 0,
            'jobs_selected': 0,
            'error': None,
        }
        try:
            discovered = connector.discover()
            attempt['jobs_available'] = len(discovered)
            by_id = {str(item.get('id')): item for item in discovered}
            selected = []
            for source_id in source.get('selected_source_job_ids') or []:
                if str(source_id) not in by_id:
                    warnings.append(f"Selected job {source_id} not present on {connector_type}:{source['board']}")
                    continue
                selected.append(by_id[str(source_id)])
            for item in selected:
                record = connector.make_raw_record(item, run_id, started_at)
                record_path = raw_dir / raw_filename(record)
                record['_output_path'] = str(record_path)
                raw_records.append(record)
            replay_id = source.get('validation_replay_source_job_id')
            if replay_id and str(replay_id) in by_id:
                replay = connector.make_raw_record(by_id[str(replay_id)], run_id, started_at, replay=True)
                replay_path = raw_dir / raw_filename(replay)
                replay['_output_path'] = str(replay_path)
                raw_records.append(replay)
            attempt['jobs_selected'] = len(selected) + (1 if replay_id and str(replay_id) in by_id else 0)
            attempt['status'] = 'SUCCESS'
            connector_types_succeeded.add(connector_type)
        except SourceAccessError as exc:
            attempt['status'] = exc.status
            attempt['error'] = str(exc)
            errors.append(str(exc))
            dump_json(raw_dir / f"SOURCE_FAILURE-{connector_type}-{source['board']}.json", {
                'run_id': run_id,
                'source_connector': connector_type,
                'board': source['board'],
                'source_api_url': connector.discovery_url,
                'retrieval_status': exc.status,
                'error': str(exc),
                'retrieved_at': started_at,
            })
        except Exception as exc:  # source failure must not terminate the run
            attempt['status'] = 'PARSING_ERROR'
            attempt['error'] = str(exc)
            errors.append(f"{connector_type}:{source['board']}: {exc}")
        source_attempts.append(attempt)

    for record in raw_records:
        output_path = Path(record.pop('_output_path'))
        dump_json(output_path, record)
        record['_output_path'] = str(output_path)

    groups, dedup_log = group_records(raw_records)
    max_unique = int(config['discovery_scope']['maximum_unique_jobs'])
    if len(groups) > max_unique:
        raise RuntimeError(f'Controlled run produced {len(groups)} unique jobs; maximum is {max_unique}.')

    existing_seen = load_seen(career_root / '08_Job_Search/Seen_Jobs') + load_seen(seen_dir)
    prior_by_id = {item['job_id']: item for item in existing_seen}
    known_job_ids = existing_ids(career_root / '10_Application_Tracker/job_index.csv')
    sequence = next_sequence(existing_seen, known_job_ids)
    normalized_jobs = []
    job_index_rows = []
    new_unique = 0

    for group in groups:
        job_id = existing_job_id(group, existing_seen)
        if job_id is None:
            title = normalize_role_title(group[0]['job_title'])
            job_id = make_job_id(discovered_date, group[0]['company'], title, sequence)
            sequence += 1
            new_unique += 1
        previous = prior_by_id.get(job_id)
        provenance_rel = f'08_Job_Search/Normalized_Jobs/{job_id}.provenance.json'
        stage3_input, provenance = build_stage3_input(group[0], job_id, discovered_date, provenance_rel)
        evaluated = evaluate_job(stage3_input, profile, sequence=1)
        normalized_path = normalized_dir / f'{job_id}.json'
        provenance_path = normalized_dir / f'{job_id}.provenance.json'
        source_urls = sorted({value for item in group for value in [item.get('source_url'), item.get('source_api_url')] if value})
        application_urls = sorted({item.get('application_link_raw') for item in group if item.get('application_link_raw')})
        provenance.update({
            'run_id': run_id,
            'discovery_status': 'READY_FOR_EVALUATION',
            'vacancy_status': 'ACTIVE',
            'primary_source': group[0]['source'],
            'source_records': [
                {
                    'raw_record_id': item['raw_record_id'],
                    'source': item['source'],
                    'source_url': item['source_url'],
                    'source_api_url': item['source_api_url'],
                    'source_job_id': item['source_job_id'],
                    'requisition_id': item.get('requisition_id'),
                    'retrieved_at': item['retrieved_at'],
                    'validation_replay': item.get('validation_replay', False),
                }
                for item in group
            ],
            'source_urls': source_urls,
            'application_urls': application_urls,
            'requisition_ids': sorted({str(item['requisition_id']) for item in group if item.get('requisition_id')}),
            'deduplication_confidence': 'EXACT_DUPLICATE' if len(group) > 1 else 'DISTINCT',
            'job_id_reused_from_seen_memory': previous is not None,
        })
        dump_json(normalized_path, evaluated)
        dump_json(provenance_path, provenance)
        normalized_jobs.append(evaluated)

        seen = build_seen_record(job_id, group, started_at, previous)
        dump_json(seen_dir / f'{job_id}.seen.json', seen)
        existing_seen.append(seen)
        prior_by_id[job_id] = seen
        for raw in group:
            raw['career_os_job_id'] = job_id
            output_path = Path(raw.pop('_output_path'))
            dump_json(output_path, raw)
            raw['_output_path'] = str(output_path)

        if evaluated['Decision'] in {'PRIORITY_APPLY', 'APPLY'}:
            shutil.copy2(normalized_path, output_root / '08_Job_Search/Shortlisted' / normalized_path.name)
        elif evaluated['Decision'] == 'SKIP':
            shutil.copy2(normalized_path, output_root / '08_Job_Search/Rejected' / normalized_path.name)

        job_index_rows.append({
            'Schema_Version': '0.1',
            'Job_ID': job_id,
            'Company': evaluated['Company'],
            'Role_Title': evaluated['Role_Title'],
            'Normalized_Role_Title': evaluated['Normalized_Role_Title'],
            'Source': evaluated['Source'],
            'Source_URL': evaluated['Source_URL'],
            'Location': evaluated['Location'],
            'Country': evaluated['Country'],
            'Date_Discovered': evaluated['Date_Discovered'],
            'Career_Direction': evaluated['Career_Direction'],
            'Recommended_Resume': evaluated['Recommended_Resume'],
            'Hard_Gate_Status': evaluated['Hard_Gate_Status'],
            'Fit_Score': evaluated['Fit_Score'],
            'Assessment_Confidence': evaluated['Assessment_Confidence'],
            'Decision': evaluated['Decision'],
            'Status': evaluated['Status'],
            'Duplicate_Group': f'DUP-{job_id}' if len(group) > 1 else '',
            'Canonical_Record': 'TRUE',
            'Normalized_Job_Path': f'08_Job_Search/Normalized_Jobs/{job_id}.json',
            'Notes': f'Stage 4 run {run_id}; discovery scope is not a candidate preference.',
        })

    for entry in dedup_log:
        ids = []
        for raw_id in entry['candidate_raw_record_ids']:
            match = next((record.get('career_os_job_id') for record in raw_records if record['raw_record_id'] == raw_id), None)
            if match:
                ids.append(match)
        entry['candidate_job_ids'] = sorted(set(ids))
    dedup_record = {
        'schema_version': '0.1',
        'run_id': run_id,
        'created_at': started_at,
        'comparisons': dedup_log,
        'exact_or_high_confidence_duplicates': sum(item['confidence'] in {'EXACT_DUPLICATE', 'HIGH_CONFIDENCE_DUPLICATE'} for item in dedup_log),
        'possible_duplicates': sum(item['confidence'] == 'POSSIBLE_DUPLICATE' for item in dedup_log),
        'auto_delete': False,
    }
    dump_json(dedup_dir / f'{run_id}_deduplication_log.json', dedup_record)
    dump_json(run_dir / 'job_index_rows.json', job_index_rows)

    ended_at = datetime.now(ZoneInfo(timezone_name)).isoformat(timespec='seconds')
    source_failures = sum(attempt['status'] != 'SUCCESS' for attempt in source_attempts)
    run_log = {
        'schema_version': '0.1',
        'run_id': run_id,
        'start_time': started_at,
        'end_time': ended_at,
        'run_status': 'PARTIAL_SUCCESS' if source_failures else 'SUCCESS',
        'source_connectors_implemented': sorted(CONNECTOR_TYPES),
        'source_connector_types_successful': sorted(connector_types_succeeded),
        'sources_attempted': source_attempts,
        'sources_successful': sum(attempt['status'] == 'SUCCESS' for attempt in source_attempts),
        'sources_failed': source_failures,
        'jobs_discovered_raw': len(raw_records),
        'jobs_normalized': len(normalized_jobs),
        'duplicates_detected': dedup_record['exact_or_high_confidence_duplicates'],
        'possible_duplicates': dedup_record['possible_duplicates'],
        'new_unique_jobs': new_unique,
        'unique_vacancies': len(groups),
        'errors': errors,
        'warnings': warnings,
        'candidate_profile_unchanged': candidate_profile_path.read_bytes() == profile_bytes,
        'application_ids_created': 0,
        'applications_submitted': 0,
    }
    dump_json(run_dir / 'discovery_run_log.json', run_log)
    print(json.dumps(run_log, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
