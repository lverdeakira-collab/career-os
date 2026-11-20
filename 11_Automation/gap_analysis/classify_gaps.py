from __future__ import annotations

from pathlib import Path
import re

from common import load_json


ALIASES_PATH = Path(__file__).with_name('skill_aliases.json')
SYNONYMS = {k.lower(): v.lower() for k, v in load_json(ALIASES_PATH)['aliases'].items()}
# A related (PARTIAL) match needs this share of the requirement's words to
# appear in one verified skill.
RELATED_OVERLAP_THRESHOLD = 0.75

CRITICAL_REQUIREMENT_TYPES = {'MUST_HAVE', 'REQUIRED', 'LANGUAGE', 'LICENSE', 'WORK_AUTHORIZATION'}


def key(value: str) -> str:
    return re.sub(r'[^a-z0-9+#/]+', ' ', value.lower()).strip()


def candidate_skill_keys(profile: dict) -> set[str]:
    values = (profile.get('verified_skills') or {}).get('all', [])
    keys = {key(value) for value in values}
    for alias, canonical in SYNONYMS.items():
        if key(canonical) in keys:
            keys.add(key(alias))
    return keys


def _confirmed_absences(profile: dict, category: str) -> set[str]:
    return {key(str(value)) for value in (profile.get('confirmed_absences') or {}).get(category, [])}


def _result(
    requirement: str,
    requirement_type: str,
    category: str,
    evidence: str | None,
    *,
    evidence_type: str = 'NONE',
    criticality: str | None = None,
    source: str | None = None,
) -> dict:
    return {
        'Requirement': requirement,
        'Requirement_Type': requirement_type,
        'Category': category,
        'Evidence': evidence,
        'Evidence_Type': evidence_type,
        'Criticality': criticality or ('CRITICAL' if requirement_type in CRITICAL_REQUIREMENT_TYPES else 'NON_CRITICAL'),
        'Source': source,
    }


def classify_requirement(
    requirement: str,
    profile: dict,
    requirement_type: str,
    *,
    requirement_present: bool = True,
    source: str | None = None,
) -> dict:
    if not requirement_present:
        return _result(requirement, requirement_type, 'NOT_APPLICABLE', None, source=source)
    value = key(requirement)
    if not value or value in {'unknown', 'unspecified', 'not specified'}:
        return _result(requirement, requirement_type, 'UNKNOWN', None, source=source)
    skills = candidate_skill_keys(profile)
    if value in skills:
        return _result(
            requirement, requirement_type, 'MATCHED', 'Candidate Profile verified skills',
            evidence_type='DIRECT', source=source,
        )
    # A verified skill named inside a longer requirement ("advanced Microsoft
    # Excel skills") is the same skill, so a detailed posting is not penalised.
    padded = f' {value} '
    contained = [candidate for candidate in skills if candidate and f' {candidate} ' in padded]
    if contained:
        return _result(
            requirement, requirement_type, 'MATCHED',
            f'Candidate Profile verified skill named in requirement: {max(contained, key=len)}',
            evidence_type='DIRECT', source=source,
        )
    tokens = set(value.split())
    best_overlap = max((len(tokens & set(candidate.split())) / max(len(tokens), 1) for candidate in skills), default=0)
    if best_overlap >= RELATED_OVERLAP_THRESHOLD:
        return _result(
            requirement, requirement_type, 'PARTIAL',
            'Related verified skill; exact scope should be reviewed', evidence_type='RELATED', source=source,
        )
    if value in _confirmed_absences(profile, 'skills'):
        return _result(
            requirement, requirement_type, 'MISSING',
            'Candidate Truth confirmed absence', evidence_type='CONFIRMED_ABSENCE', source=source,
        )
    return _result(
        requirement, requirement_type, 'UNKNOWN', None,
        evidence_type='INSUFFICIENT_EVIDENCE', source=source,
    )


def _language_gap(assessment: dict) -> dict:
    classification = assessment['classification']
    criticality = 'CRITICAL' if classification in {'REQUIRED', 'DISQUALIFYING'} else 'NON_CRITICAL'
    return _result(
        assessment['language'],
        'LANGUAGE' if criticality == 'CRITICAL' else 'PREFERRED',
        assessment['gap_status'],
        assessment.get('candidate_evidence'),
        evidence_type='LANGUAGE_EVIDENCE',
        criticality=criticality,
        source=assessment.get('source_text'),
    )


def _work_authorization_gap(assessment: dict) -> dict | None:
    signal = assessment['work_authorization_signal']
    if signal == 'NOT_STATED':
        return None
    effect = assessment['hard_gate_effect']
    ignored = assessment.get('user_action') == 'IGNORE' and not (assessment.get('candidate_evidence') or {}).get('country_authorized')
    if effect == 'CRITICAL_HARD_REQUIREMENT_MISSING':
        status = 'MISSING'
    elif ignored:
        status = 'NOT_APPLICABLE'
    elif effect == 'NONE' and signal not in {'LOCAL_CANDIDATES_PREFERRED', 'EXISTING_AUTHORIZATION_PREFERRED'}:
        status = 'MATCHED'
    elif signal in {'LOCAL_CANDIDATES_PREFERRED', 'EXISTING_AUTHORIZATION_PREFERRED'}:
        status = 'NOT_APPLICABLE'
    else:
        status = 'UNKNOWN'
    return _result(
        assessment['policy_interpretation'], 'WORK_AUTHORIZATION', status,
        str(assessment.get('candidate_evidence') or '') or None,
        evidence_type='WORK_AUTHORIZATION_EVIDENCE', criticality='CRITICAL',
        source=assessment.get('source_text'),
    )


def analyze_gaps(
    job: dict,
    profile: dict,
    work_authorization: dict | None = None,
    language_assessments: list[dict] | None = None,
) -> list[dict]:
    gaps = []
    for field, requirement_type in [
        ('Must_Have_Skills', 'MUST_HAVE'),
        ('Required_Skills', 'REQUIRED'),
        ('Preferred_Skills', 'PREFERRED'),
    ]:
        for requirement in job.get(field) or []:
            gaps.append(classify_requirement(requirement, profile, requirement_type, source=field))

    evidence_tags = (profile.get('verified_skills') or {}).get('evidence_tags', {})
    direct = {key(str(tag)) for tag in evidence_tags.get('direct', [])}
    transferable = {key(str(tag)) for tag in evidence_tags.get('transferable', [])}
    confirmed_absent_tags = _confirmed_absences(profile, 'responsibility_tags')
    for tag in job.get('Responsibility_Tags') or []:
        # Every comparison uses the same normalized key, so case and
        # punctuation never change the result.
        normalized_tag = key(str(tag))
        if normalized_tag in direct:
            category, evidence, evidence_type = 'MATCHED', 'Candidate Profile direct evidence tag', 'DIRECT'
        elif normalized_tag in transferable:
            category, evidence, evidence_type = 'PARTIAL', 'Candidate Profile transferable evidence tag', 'TRANSFERABLE'
        elif not normalized_tag or normalized_tag.startswith('unknown'):
            category, evidence, evidence_type = 'UNKNOWN', None, 'INSUFFICIENT_EVIDENCE'
        elif normalized_tag in confirmed_absent_tags:
            category, evidence, evidence_type = 'MISSING', 'Candidate Truth confirmed absence', 'CONFIRMED_ABSENCE'
        else:
            category, evidence, evidence_type = 'UNKNOWN', None, 'INSUFFICIENT_EVIDENCE'
        gaps.append(_result(
            tag, 'RESPONSIBILITY', category, evidence,
            evidence_type=evidence_type, criticality='NON_CRITICAL', source='Responsibility_Tags',
        ))

    verified_licenses = {key(value) for value in profile.get('professional_licenses') or []}
    absent_licenses = _confirmed_absences(profile, 'professional_licenses')
    for license_name in job.get('Mandatory_Licenses') or []:
        normalized = key(license_name)
        if normalized in verified_licenses:
            category, evidence, evidence_type = 'MATCHED', 'Candidate Profile professional licenses', 'DIRECT'
        elif normalized in absent_licenses:
            category, evidence, evidence_type = 'MISSING', 'Candidate Truth confirmed absence', 'CONFIRMED_ABSENCE'
        else:
            category, evidence, evidence_type = 'UNKNOWN', None, 'INSUFFICIENT_EVIDENCE'
        gaps.append(_result(
            license_name, 'LICENSE', category, evidence,
            evidence_type=evidence_type, criticality='CRITICAL', source='Mandatory_Licenses',
        ))

    for assessment in language_assessments or []:
        if assessment['classification'] != 'UNKNOWN':
            gaps.append(_language_gap(assessment))
    if work_authorization:
        work_gap = _work_authorization_gap(work_authorization)
        if work_gap:
            gaps.append(work_gap)
    return gaps
