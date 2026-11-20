from __future__ import annotations

import re


UNTRUSTED_INSTRUCTION_PATTERNS = [
    ('IGNORE_RULES', r'\bignore (?:all |any )?(?:previous|prior|system) instructions?\b'),
    ('UPLOAD_REQUEST', r'\bupload (?:this |a |your )?(?:file|resume|cv|document)\b'),
    ('CREDENTIAL_REQUEST', r'\b(?:send|share|reveal|enter) (?:your )?(?:credentials?|password|api key|secret)\b'),
    ('PROFILE_MUTATION_REQUEST', r'\b(?:change|modify|update) (?:your |the )?candidate profile\b'),
    ('LOCAL_FILE_REQUEST', r'\b(?:reveal|send|read|list) (?:your )?local files?\b'),
    ('EXTERNAL_ACTION_REQUEST', r'\b(?:visit|open|click) (?:this |the )?(?:link|url)\b'),
]


def detect_untrusted_instructions(job: dict) -> list[dict]:
    text = job.get('Job_Description_Raw') or job.get('Job_Description_Clean') or ''
    findings = []
    for code, pattern in UNTRUSTED_INSTRUCTION_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            findings.append({
                'code': code,
                'source_text': match.group(0),
                'treatment': 'UNTRUSTED_JOB_TEXT_ONLY',
                'executed': False,
            })
    return findings
