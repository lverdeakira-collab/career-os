"""Classify language requirements in a posting against the candidate's stated
languages. How a missing or unverified required language is handled is a
user preference (see preferences.py)."""

from __future__ import annotations

from pathlib import Path
import re

from common import load_json

from .preferences import effect_for, load_preferences


CONFIG_PATH = Path(__file__).with_name('language_aliases.json')


def _language_mentions(text: str, aliases: dict[str, str]) -> list[tuple[str, str]]:
    found = []
    lowered = text.lower()
    for token, canonical in aliases.items():
        if re.search(rf'\b{re.escape(token)}\b', lowered):
            found.append((token, canonical))
    unique = []
    seen = set()
    for item in found:
        if item[1] not in seen:
            seen.add(item[1])
            unique.append(item)
    return unique


def _candidate_language_state(profile: dict, canonical: str, require_proficiency: bool = False) -> tuple[str, str | None]:
    confirmed_absent = {
        str(value).lower()
        for value in (profile.get('confirmed_absences') or {}).get('languages', [])
    }
    if canonical.lower() in confirmed_absent:
        return 'MISSING', 'Candidate Truth confirms the language is absent.'
    for item in profile.get('languages') or []:
        if str(item.get('language') or '').lower() == canonical.lower():
            if item.get('proficiency'):
                return 'MATCHED', f"Candidate Truth: {canonical} ({item['proficiency']})"
            if require_proficiency:
                return 'PARTIAL', f'Candidate Truth lists {canonical}; the requested proficiency level is unverified.'
            return 'MATCHED', f'Candidate Truth lists {canonical}; no proficiency level is requested.'
    return 'UNKNOWN', None


def _effect(gap_status: str, preferences: dict) -> str:
    if gap_status == 'MISSING':
        return effect_for(preferences['required_language_missing'], confirmed=True)
    if gap_status in {'UNKNOWN', 'PARTIAL'}:
        return effect_for(preferences['required_language_unverified'], confirmed=False)
    return 'NONE'


def classify_language_requirements(job: dict, profile: dict, strategy: dict | None = None) -> list[dict]:
    preferences = load_preferences(strategy)
    config = load_json(CONFIG_PATH)
    aliases = config['language_aliases']
    structured_required = job.get('Mandatory_Languages') or []
    free_text = job.get('Language_Requirements') or ''
    jd_text = job.get('Job_Description_Clean') or ''
    assessments = []

    for raw_language in structured_required:
        canonical = aliases.get(str(raw_language).lower(), str(raw_language))
        proficiency_required = bool(re.search(
            rf'\b(?:good command|proficien(?:t|cy)|fluen(?:t|cy)|native|business[- ]level)\b.{{0,60}}\b{re.escape(str(raw_language))}\b|'
            rf'\b{re.escape(str(raw_language))}\b.{{0,60}}\b(?:good command|proficien(?:t|cy)|fluen(?:t|cy)|native|business[- ]level)\b',
            free_text,
            flags=re.IGNORECASE,
        ))
        gap_status, evidence = _candidate_language_state(profile, canonical, proficiency_required)
        assessments.append({
            'language': canonical,
            'classification': 'REQUIRED',
            'source_text': str(raw_language),
            'gap_status': gap_status,
            'candidate_evidence': evidence,
            'hard_gate_effect': _effect(gap_status, preferences),
            'confidence': 'HIGH',
        })

    combined = free_text or jd_text
    for token, canonical in _language_mentions(combined, aliases):
        if any(item['language'].lower() == canonical.lower() for item in assessments):
            continue
        window_pattern = rf'.{{0,100}}\b{re.escape(token)}\b.{{0,100}}'
        match = re.search(window_pattern, combined, flags=re.IGNORECASE)
        source = match.group(0).strip() if match else token
        lowered = source.lower()
        if re.search(r'\b(native|mother tongue|only)\b', lowered):
            classification = 'DISQUALIFYING'
        elif re.search(r'\b(required|must|mandatory|essential|proficien(?:t|cy)|fluen(?:t|cy)|good command)\b', lowered):
            classification = 'REQUIRED'
        elif re.search(r'\b(preferred|advantage|plus|desirable|nice to have)\b', lowered):
            classification = 'PREFERRED'
        elif re.search(r'\b(market|clients?|customers?|region|coverage|liais|stakeholders?)\b', lowered):
            classification = 'BUSINESS_CONTEXT'
        else:
            classification = 'UNKNOWN'
        proficiency_required = bool(re.search(r'\b(native|mother tongue|proficien(?:t|cy)|fluen(?:t|cy)|good command|business[- ]level)\b', lowered))
        gap_status, evidence = _candidate_language_state(profile, canonical, proficiency_required)
        critical = classification in {'REQUIRED', 'DISQUALIFYING'}
        effect = _effect(gap_status, preferences) if critical else 'NONE'
        assessments.append({
            'language': canonical,
            'classification': classification,
            'source_text': source,
            'gap_status': gap_status if classification not in {'BUSINESS_CONTEXT', 'UNKNOWN'} else 'NOT_APPLICABLE',
            'candidate_evidence': evidence,
            'hard_gate_effect': effect,
            'confidence': 'HIGH' if classification != 'UNKNOWN' else 'LOW',
        })
    return assessments
