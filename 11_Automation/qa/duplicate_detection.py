from __future__ import annotations

from difflib import SequenceMatcher
import re


def _norm(value: str | None) -> str:
    return re.sub(r'\W+', ' ', value or '').strip().lower()


def duplicate_reason(a: dict, b: dict) -> str | None:
    if a.get('Source_URL') and b.get('Source_URL') and a['Source_URL'].rstrip('/') == b['Source_URL'].rstrip('/'):
        return 'EXACT_URL'
    same_identity = (
        _norm(a.get('Company')) == _norm(b.get('Company'))
        and _norm(a.get('Normalized_Role_Title')) == _norm(b.get('Normalized_Role_Title'))
        and _norm(a.get('Location')) == _norm(b.get('Location'))
    )
    if same_identity:
        return 'COMPANY_ROLE_LOCATION'
    text_a = _norm(a.get('Job_Description_Clean'))
    text_b = _norm(b.get('Job_Description_Clean'))
    if text_a and text_b and SequenceMatcher(None, text_a, text_b).ratio() >= 0.86:
        if _norm(a.get('Company')) == _norm(b.get('Company')):
            return 'HIGHLY_SIMILAR_REPOST'
    return None


def assign_duplicate_groups(records: list[dict]) -> list[dict]:
    records = [dict(record) for record in records]
    group_number = 1
    used = set()
    for i, record in enumerate(records):
        if i in used:
            continue
        members = [i]
        for j in range(i + 1, len(records)):
            if duplicate_reason(record, records[j]):
                members.append(j)
        if len(members) > 1:
            group = f'DUP-{group_number:04d}'
            canonical = min((records[index] for index in members), key=lambda item: (item.get('Date_Discovered') or '', item['Job_ID']))
            for index in members:
                records[index]['Duplicate_Group'] = group
                records[index]['Duplicate_Canonical_Job_ID'] = canonical['Job_ID']
                used.add(index)
            group_number += 1
    return records
