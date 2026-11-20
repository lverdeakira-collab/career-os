from __future__ import annotations

from difflib import SequenceMatcher
from hashlib import sha256
import re


def compact(value: str | None) -> str:
    return re.sub(r'[^a-z0-9]+', '', (value or '').lower())


def jd_fingerprint(record: dict) -> str:
    clean = ' '.join((record.get('job_description_raw') or '').lower().split())
    return sha256(clean.encode('utf-8')).hexdigest()


def _similarity(left: dict, right: dict) -> float:
    a = ' '.join((left.get('job_description_raw') or '').lower().split())
    b = ' '.join((right.get('job_description_raw') or '').lower().split())
    return SequenceMatcher(None, a, b, autojunk=False).ratio() if a and b else 0.0


def compare_records(left: dict, right: dict) -> dict:
    same_company = compact(left.get('company')) == compact(right.get('company'))
    same_title = compact(left.get('job_title')) == compact(right.get('job_title'))
    same_location = compact(left.get('location_raw')) == compact(right.get('location_raw'))
    same_source_id = left.get('source_connector') == right.get('source_connector') and left.get('source_job_id') == right.get('source_job_id')
    same_requisition = same_company and left.get('requisition_id') and left.get('requisition_id') == right.get('requisition_id')
    similarity = _similarity(left, right)
    features = {
        'same_source_job_id': bool(same_source_id),
        'same_company_requisition_id': bool(same_requisition),
        'same_company': same_company,
        'same_title': same_title,
        'same_location': same_location,
        'jd_similarity': round(similarity, 4),
    }
    if same_source_id or same_requisition:
        return {'decision': 'MERGE', 'confidence': 'EXACT_DUPLICATE', 'matching_features': features, 'reason': 'Exact source/ATS identifier match.'}
    if same_company and same_title and same_location and similarity >= 0.94:
        return {'decision': 'MERGE', 'confidence': 'HIGH_CONFIDENCE_DUPLICATE', 'matching_features': features, 'reason': 'Company, title, location, and materially identical JD match.'}
    if same_company and same_title and same_location and similarity >= 0.55:
        return {'decision': 'REVIEW', 'confidence': 'POSSIBLE_DUPLICATE', 'matching_features': features, 'reason': 'Identity fields match but JD evidence is not sufficient for auto-merge.'}
    return {'decision': 'KEEP_SEPARATE', 'confidence': 'DISTINCT', 'matching_features': features, 'reason': 'No strong vacancy-level identity match.'}


def group_records(records: list[dict]) -> tuple[list[list[dict]], list[dict]]:
    groups: list[list[dict]] = []
    log: list[dict] = []
    for record in records:
        merged = False
        for group in groups:
            comparison = compare_records(group[0], record)
            if comparison['confidence'] != 'DISTINCT':
                log.append({
                    'candidate_raw_record_ids': [group[0]['raw_record_id'], record['raw_record_id']],
                    'source_records': [group[0]['source_url'], record['source_url']],
                    **comparison,
                })
            if comparison['decision'] == 'MERGE':
                group.append(record)
                merged = True
                break
        if not merged:
            groups.append([record])
    return groups, log
