from __future__ import annotations

from datetime import datetime, timezone
import re


COUNTRY_CODES = {'SG': 'Singapore', 'CN': 'China', 'HK': 'Hong Kong', 'MY': 'Malaysia', 'US': 'United States'}
SKILL_PATTERNS = {
    'Microsoft Excel': [r'\bexcel\b'],
    'Microsoft PowerPoint': [r'\bpowerpoint\b'],
    'Python': [r'\bpython\b'],
    'SQL': [r'\bsql\b'],
    'Power BI': [r'\bpower\s*bi\b'],
    'Tableau': [r'\btableau\b'],
    'Data Visualization': [r'data visuali[sz]ation'],
    'Financial Modelling': [r'financial model(?:ing|ling)'],
    'DCF Valuation': [r'\bdcf\b|discounted cash flow'],
    'Risk Analysis': [r'risk analys'],
    'Market Research': [r'market research'],
    'Generative AI / GPT': [r'generative ai|\bgpt\b|large language model|\bllm\b'],
}
PREFERRED_MARKERS = ('preferred', 'advantage', 'plus', 'desirable', 'nice to have', 'bonus')
MANDATORY_MARKERS = (' must ', 'required', 'mandatory', 'essential', 'minimum', 'is a must')
RESPONSIBILITY_HEADINGS = ('responsibil', 'what you will do', "what you'll do", 'your adventure', 'the role', 'key duties')
REQUIREMENT_HEADINGS = ('requirement', 'qualification', 'essentials', 'what you bring', 'who should apply', 'skills required')
PREFERRED_HEADINGS = ('preferred', 'nice to have', 'bonus')


def _iso_date(value) -> str | None:
    if value is None or value == '':
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()
    text = str(value).strip()
    match = re.match(r'^(\d{4}-\d{2}-\d{2})', text)
    return match.group(1) if match else None


def _country(raw: dict) -> str | None:
    code = str((raw.get('source_metadata') or {}).get('country_code') or '').upper()
    if code in COUNTRY_CODES:
        return COUNTRY_CODES[code]
    location = (raw.get('location_raw') or '').lower()
    for country in ['Singapore', 'China', 'Hong Kong', 'Malaysia', 'United States', 'Japan', 'Thailand']:
        if country.lower() in location:
            return country
    address = ((raw.get('source_metadata') or {}).get('address') or {}).get('postalAddress') or {}
    return address.get('addressCountry')


def _remote_status(raw: dict) -> str:
    metadata = raw.get('source_metadata') or {}
    workplace = str(metadata.get('workplace_type') or '').lower()
    if workplace in {'remote', 'hybrid', 'onsite', 'on-site'}:
        return {'remote': 'REMOTE', 'hybrid': 'HYBRID', 'onsite': 'ONSITE', 'on-site': 'ONSITE'}[workplace]
    if metadata.get('is_remote') is True:
        return 'REMOTE'
    return 'UNKNOWN'


def _lines(text: str) -> list[str]:
    return [' '.join(line.split()) for line in text.splitlines() if line.strip()]


def _extract_sections(text: str) -> tuple[list[str], list[str], list[str]]:
    responsibilities, required, preferred = [], [], []
    mode = None
    for line in _lines(text):
        lowered = line.lower().strip(':')
        if len(line) <= 90 and any(marker in lowered for marker in PREFERRED_HEADINGS):
            mode = 'preferred'; continue
        if len(line) <= 90 and any(marker in lowered for marker in REQUIREMENT_HEADINGS):
            mode = 'required'; continue
        if len(line) <= 90 and any(marker in lowered for marker in RESPONSIBILITY_HEADINGS):
            mode = 'responsibilities'; continue
        if len(line) < 20:
            continue
        if mode == 'responsibilities':
            responsibilities.append(line)
        elif mode == 'required':
            required.append(line)
        elif mode == 'preferred':
            preferred.append(line)
    return responsibilities[:30], required[:30], preferred[:30]


def _extract_skills(required_lines: list[str], preferred_lines: list[str], full_text: str) -> tuple[list[str], list[str], list[str]]:
    required_skills, preferred_skills, must_have = [], [], []
    pools = [('REQUIRED', required_lines), ('PREFERRED', preferred_lines)]
    if not required_lines and not preferred_lines:
        pools = [('REQUIRED', _lines(full_text))]
    for kind, lines in pools:
        for line in lines:
            lowered = f' {line.lower()} '
            for skill, patterns in SKILL_PATTERNS.items():
                if any(re.search(pattern, lowered) for pattern in patterns):
                    target = preferred_skills if kind == 'PREFERRED' or any(marker in lowered for marker in PREFERRED_MARKERS) else required_skills
                    if skill not in target:
                        target.append(skill)
                    if target is required_skills and any(marker in lowered for marker in MANDATORY_MARKERS) and skill not in must_have:
                        must_have.append(skill)
    return required_skills, preferred_skills, must_have


def _extract_languages(text: str, required_lines: list[str], preferred_lines: list[str]) -> tuple[str | None, list[str]]:
    languages = ['English', 'Chinese', 'Mandarin', 'Japanese', 'Thai', 'Korean']
    evidence, mandatory = [], []
    required_set = set(required_lines)
    preferred_set = set(preferred_lines)
    for line in _lines(text):
        found = [language for language in languages if re.search(rf'\b{language.lower()}\b', line.lower())]
        if not found:
            continue
        evidence.append(line)
        lowered = f' {line.lower()} '
        is_preferred = line in preferred_set or any(marker in lowered for marker in PREFERRED_MARKERS)
        is_required = line in required_set or any(marker in lowered for marker in MANDATORY_MARKERS) or any(token in lowered for token in ('fluent', 'proficiency', 'business-level', 'native-level', 'good command'))
        if is_required and not is_preferred:
            for language in found:
                if language not in mandatory:
                    mandatory.append(language)
    return (' | '.join(evidence[:6]) or None), mandatory


NON_CANDIDATE_DURATION_PATTERNS = (
    r'\bbuilding on (?:more than |over )?\d+(?:\.\d+)? years?\b',
    r'\bfounded\b.{0,80}\b\d+(?:\.\d+)? years?\b',
    r'\b(?:company|firm|platform|business|organisation|organization)\b.{0,40}'
    r'\b(?:has|have|with|brings?|boasts?)\b.{0,25}\b\d+(?:\.\d+)? years?\b',
    r'\b\d+(?:\.\d+)?[- ]year (?:company|firm|business|market|product|project|program|programme|contract) history\b',
    r'\b(?:in business|serving (?:clients|customers|members)) for \d+(?:\.\d+)? years?\b',
)

EXPERIENCE_PREFIX_PATTERN = re.compile(
    r'\bexperience\s*:\s*'
    r'(?P<approx>approximately|approx\.?|about|around)?\s*'
    r'(?P<minimum>\d+(?:\.\d+)?)\s*'
    r'(?:(?P<plus>\+)|(?:to|[-–—])\s*(?P<maximum>\d+(?:\.\d+)?))?\s*years?\b',
    re.IGNORECASE,
)

EXPERIENCE_PHRASE_PATTERN = re.compile(
    r'(?P<approx>approximately|approx\.?|about|around)?\s*'
    r'(?P<minimum>\d+(?:\.\d+)?)\s*'
    r'(?:(?P<plus>\+)|(?:to|[-–—])\s*(?P<maximum>\d+(?:\.\d+)?))?\s*'
    r'years?\s*(?:of)?\s*'
    r'(?:(?:progressive|relevant|professional|work|industry|hands-on|prior)\s+){0,3}'
    r'experience\b',
    re.IGNORECASE,
)


def _non_candidate_duration(line: str) -> bool:
    return any(re.search(pattern, line, re.IGNORECASE) for pattern in NON_CANDIDATE_DURATION_PATTERNS)


def _experience_match(line: str) -> re.Match | None:
    if _non_candidate_duration(line):
        return None
    return EXPERIENCE_PREFIX_PATTERN.search(line) or EXPERIENCE_PHRASE_PATTERN.search(line)


def _extract_experience_requirement(text: str) -> dict:
    candidates = []
    for line in _lines(text):
        match = _experience_match(line)
        if not match:
            continue
        minimum = float(match.group('minimum'))
        maximum = float(match.group('maximum')) if match.group('maximum') else None
        candidates.append({
            'status': 'EXPLICIT',
            'minimum_years': minimum,
            'maximum_years': maximum,
            'open_ended_minimum': bool(match.group('plus')),
            'approximate': bool(match.group('approx')),
            'source_text': line,
        })
    if not candidates:
        return {
            'status': 'UNKNOWN',
            'minimum_years': None,
            'maximum_years': None,
            'open_ended_minimum': False,
            'approximate': False,
            'source_text': None,
        }
    return min(candidates, key=lambda item: item['minimum_years'])


def _extract_years(text: str) -> float | None:
    """Return the backward-compatible minimum/anchor used by the Stage 3 gate."""
    return _extract_experience_requirement(text)['minimum_years']


def _tags(responsibilities: list[str]) -> list[str]:
    joined = ' '.join(responsibilities).lower()
    mapping = {
        'financial_analysis': ('financial analysis', 'financial performance', 'financial model'),
        'market_research': ('market research', 'market intelligence'),
        'business_strategy': ('business strategy', 'strategic planning', 'strategy'),
        'business_reporting': ('reporting', 'management report'),
        'data_analysis': ('data analysis', 'analytics', 'analyze data', 'analyse data'),
        'banking_operations': ('banking operations', 'middle office', 'onboarding', 'account opening'),
        'risk_analysis': ('risk analysis', 'risk management'),
        'stakeholder_coordination': ('stakeholder', 'cross-functional', 'coordinate'),
        'ai_adoption': ('ai adoption', 'generative ai', 'automation'),
    }
    return [tag for tag, terms in mapping.items() if any(term in joined for term in terms)]


def build_stage3_input(raw: dict, job_id: str, discovered_date: str, provenance_path: str) -> tuple[dict, dict]:
    text = raw.get('job_description_raw') or ''
    experience_requirement = _extract_experience_requirement(text)
    responsibilities, required_qualifications, preferred_qualifications = _extract_sections(text)
    required_skills, preferred_skills, must_have = _extract_skills(required_qualifications, preferred_qualifications, text)
    language_text, mandatory_languages = _extract_languages(text, required_qualifications, preferred_qualifications)
    education_lines = [line for line in required_qualifications + preferred_qualifications if re.search(r'\b(bachelor|master|degree|mba|phd)\b', line, re.I)]
    mandatory_education = [line for line in education_lines if line in required_qualifications and any(marker in f' {line.lower()} ' for marker in MANDATORY_MARKERS)]
    work_auth_lines = [line for line in _lines(text) if re.search(r'sponsor|work authori[sz]ation|right to work|work permit|visa', line, re.I)]
    stage3 = {
        'Job_ID': job_id,
        'Source': raw.get('source'),
        'Source_URL': raw.get('source_url'),
        'Company': raw.get('company'),
        'Role_Title': raw.get('job_title'),
        'Location': raw.get('location_raw'),
        'Country': _country(raw),
        'Remote_Status': _remote_status(raw),
        'Employment_Type': raw.get('employment_type_raw'),
        'Seniority': raw.get('seniority_raw'),
        'Business_Function': raw.get('department_raw'),
        'Industry': None,
        'Date_Posted': _iso_date(raw.get('posting_date_raw')),
        'Date_Discovered': discovered_date,
        'Job_Description_Raw': text,
        'Job_Description_Clean': ' '.join(text.split()),
        'Responsibilities': responsibilities,
        'Responsibility_Tags': _tags(responsibilities),
        'Required_Qualifications': required_qualifications,
        'Preferred_Qualifications': preferred_qualifications,
        'Required_Skills': required_skills,
        'Preferred_Skills': preferred_skills,
        'Must_Have_Skills': must_have,
        'Required_Experience_Years': experience_requirement['minimum_years'],
        'Required_Experience_Requirement': experience_requirement,
        'cover_letter_requirement': 'UNKNOWN',
        'Language_Requirements': language_text,
        'Mandatory_Languages': mandatory_languages,
        'Education_Requirements': ' | '.join(education_lines[:6]) or None,
        'Mandatory_Education': mandatory_education[:6],
        'Work_Authorization_Notes': ' | '.join(work_auth_lines[:4]) or None,
        'Sponsorship_Available': 'NO' if any('no sponsorship' in line.lower() for line in work_auth_lines) else 'UNKNOWN',
        'Mandatory_Licenses': [],
        'Salary': None,
        'Application_Deadline': _iso_date((raw.get('source_payload') or {}).get('application_deadline')),
        'Recruiter_Name': None,
        'Recruiter_Contact': None,
        'Notes': f'Stage 4 provenance: {provenance_path}',
        'Synthetic_Test': False,
    }
    provenance = {
        'schema_version': '0.1',
        'job_id': job_id,
        'normalization_status': 'SUCCESS',
        'field_provenance': {
            field: {
                'value': value,
                'source': raw.get('source'),
                'source_url': raw.get('source_url'),
                'raw_record_id': raw.get('raw_record_id'),
                'extraction_method': 'DIRECT' if field in {'Company', 'Role_Title', 'Location', 'Employment_Type', 'Date_Posted', 'Job_Description_Raw'} else 'DETERMINISTIC_RULE',
                'confidence': 'HIGH' if value not in (None, '', [], 'UNKNOWN') else 'LOW',
            }
            for field, value in stage3.items()
            if field not in {'Job_ID', 'Notes', 'Synthetic_Test'}
        },
    }
    return stage3, provenance
