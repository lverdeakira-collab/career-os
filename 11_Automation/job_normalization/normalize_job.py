from __future__ import annotations

from copy import deepcopy
from datetime import date
import re

from common import clean_space, slug


JOB_FIELDS = [
    'Schema_Version', 'Job_ID', 'Source', 'Source_URL', 'Company', 'Role_Title', 'Normalized_Role_Title',
    'Location', 'Country', 'Remote_Status', 'Employment_Type', 'Seniority', 'Business_Function', 'Industry',
    'Date_Posted', 'Date_Discovered', 'Job_Description_Raw', 'Job_Description_Clean', 'Responsibilities',
    'Responsibility_Tags', 'Required_Qualifications', 'Preferred_Qualifications', 'Required_Skills',
    'Preferred_Skills', 'Must_Have_Skills', 'Required_Experience_Years', 'Language_Requirements',
    'Required_Experience_Requirement', 'cover_letter_requirement',
    'Mandatory_Languages', 'Education_Requirements', 'Mandatory_Education', 'Work_Authorization_Notes',
    'Sponsorship_Available', 'Mandatory_Licenses', 'Salary', 'Application_Deadline', 'Recruiter_Name',
    'Recruiter_Contact', 'Career_Direction', 'Primary_Route', 'Secondary_Route', 'Routing_Confidence',
    'Recommended_Resume', 'Hard_Gate_Status', 'Hard_Gate_Reasons', 'Fit_Score', 'Fit_Score_Breakdown',
    'Assessment_Confidence', 'Top_Matches', 'Gaps', 'Fit_Explanation', 'Decision', 'Gap_Count', 'Status', 'Duplicate_Group',
    'Duplicate_Canonical_Job_ID', 'Notes', 'Synthetic_Test',
    'Hardening_Version', 'Primary_Resume', 'Primary_Reason', 'Optional_Secondary_Resume',
    'Secondary_Reason', 'Secondary_Allowed', 'Routing_Human_Review_Required', 'Base_Selection_Scores',
    'Work_Authorization_Assessment', 'Language_Assessments',
    'Circuit_Breaker', 'Prompt_Injection_Signals'
]

ARRAY_FIELDS = {
    'Responsibilities', 'Responsibility_Tags', 'Required_Qualifications', 'Preferred_Qualifications',
    'Required_Skills', 'Preferred_Skills', 'Must_Have_Skills', 'Mandatory_Languages',
    'Mandatory_Education', 'Mandatory_Licenses', 'Hard_Gate_Reasons', 'Top_Matches', 'Gaps',
    'Language_Assessments', 'Prompt_Injection_Signals'
}

DEFAULTS = {field: ([] if field in ARRAY_FIELDS else None) for field in JOB_FIELDS}
DEFAULTS.update({
    'Schema_Version': '0.1',
    'Job_Description_Raw': '',
    'Job_Description_Clean': '',
    'Status': 'DISCOVERED',
    'Remote_Status': 'UNKNOWN',
    'Sponsorship_Available': 'UNKNOWN',
    'Synthetic_Test': False,
    'Hardening_Version': '1.0',
    'cover_letter_requirement': 'UNKNOWN',
    'Secondary_Allowed': False,
    'Routing_Human_Review_Required': False,
})

TITLE_RULES = [
    (r'\bcommercial finance analyst\b|\bbusiness finance analyst\b', 'Commercial Finance Analyst'),
    (r'\b(junior\s+)?financial analyst\b|\bfinance analyst\b|\bfp&a analyst\b', 'Financial Analyst'),
    (r'\bvaluation analyst\b', 'Valuation Analyst'),
    (r'\bcredit risk analyst\b|\bcredit analyst\b', 'Credit Analyst'),
    (r'\boperational risk analyst\b', 'Operational Risk Analyst'),
    (r'\bcorporate banking analyst\b|\bcommercial banking analyst\b', 'Corporate Banking Analyst'),
    (r'\bkyc\b|\baml\b|\bfinancial crime analyst\b', 'KYC / AML Analyst'),
    (r'\bstrategy analyst\b|\bbusiness strategy analyst\b|\bcorporate strategy analyst\b', 'Strategy Analyst'),
    (r'\bmarket intelligence analyst\b|\bcompetitive intelligence analyst\b', 'Market Intelligence Analyst'),
    (r'\bbusiness analyst\b', 'Business Analyst'),
    (r'\bbusiness analytics analyst\b|\bdata analyst\b|\bbi analyst\b|\bbusiness intelligence analyst\b', 'Business Analytics Analyst'),
    (r'\boperations analyst\b|\breporting analyst\b|\bperformance analyst\b', 'Operations Analyst'),
    (r'\bai transformation analyst\b|\bdigital transformation analyst\b', 'AI Transformation Analyst'),
    (r'\bai business analyst\b|\bai strategy analyst\b|\bai operations analyst\b', 'AI Business Analyst'),
    (r'\bautomation analyst\b|\bai enablement analyst\b', 'Automation Analyst'),
    (r'\bsoftware engineer\b|\bmachine learning engineer\b|\bml engineer\b', 'Software / ML Engineer'),
]


def normalize_role_title(role_title: str) -> str:
    title = clean_space(role_title)
    lowered = title.lower()
    for pattern, normalized in TITLE_RULES:
        if re.search(pattern, lowered):
            return normalized
    return title


def classify_seniority(role_title: str, supplied: str | None) -> str | None:
    if supplied:
        return supplied
    value = role_title.lower()
    ordered = [
        ('senior manager', 'Senior Manager'), ('senior associate', 'Senior Associate'),
        ('director', 'Director'), ('manager', 'Manager'), ('executive', 'Executive'),
        ('junior associate', 'Junior Associate'), ('associate', 'Associate'),
        ('graduate', 'Graduate'), ('entry level', 'Entry Level'), ('intern', 'Intern'),
        ('junior', 'Entry Level'), ('analyst', 'Analyst'),
    ]
    return next((label for token, label in ordered if token in value), None)


def make_job_id(date_discovered: str, company: str, normalized_role: str, sequence: int) -> str:
    stamp = date_discovered.replace('-', '')
    if not re.fullmatch(r'[0-9]{8}', stamp):
        raise ValueError('Date_Discovered must use YYYY-MM-DD')
    if sequence < 1 or sequence > 9999:
        raise ValueError('sequence must be between 1 and 9999')
    return f'JOB-{stamp}-{slug(company)}-{slug(normalized_role)}-{sequence:04d}'


def normalize_job(raw: dict, sequence: int = 1) -> dict:
    job = deepcopy(DEFAULTS)
    unknown_fields = sorted(set(raw) - set(JOB_FIELDS))
    if unknown_fields:
        raise ValueError(f'Unknown job fields: {unknown_fields}')
    job.update(deepcopy(raw))
    job['Schema_Version'] = '0.1'
    job['Company'] = clean_space(job.get('Company'))
    job['Role_Title'] = clean_space(job.get('Role_Title'))
    if not job['Company'] or not job['Role_Title']:
        raise ValueError('Company and Role_Title are required; use explicit synthetic labels for tests')
    job['Normalized_Role_Title'] = normalize_role_title(job['Role_Title'])
    job['Date_Discovered'] = job.get('Date_Discovered') or date.today().isoformat()
    job['Job_ID'] = job.get('Job_ID') or make_job_id(
        job['Date_Discovered'], job['Company'], job['Normalized_Role_Title'], sequence
    )
    job['Seniority'] = classify_seniority(job['Role_Title'], job.get('Seniority'))
    raw_jd = clean_space(job.get('Job_Description_Raw'))
    clean_jd = clean_space(job.get('Job_Description_Clean')) or raw_jd
    job['Job_Description_Raw'] = raw_jd
    job['Job_Description_Clean'] = clean_jd
    for field in ARRAY_FIELDS:
        if job.get(field) is None:
            job[field] = []
    job['Status'] = 'NORMALIZED'
    return {field: job[field] for field in JOB_FIELDS}
