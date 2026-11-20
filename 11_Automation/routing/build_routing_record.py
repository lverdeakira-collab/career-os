from __future__ import annotations

from urllib.parse import urlparse


ATS_PROVIDERS = frozenset({
    'LEVER', 'GREENHOUSE', 'ASHBY', 'WORKDAY', 'SUCCESSFACTORS',
    'SMARTRECRUITERS', 'ICIMS', 'COMPANY_CAREERS_OTHER', 'UNKNOWN',
})

VERIFICATION_STATUSES = frozenset({
    'VERIFIED_ACTIVE', 'VERIFIED_REMOVED_OR_CLOSED', 'NOT_YET_VERIFIED', 'VERIFICATION_FAILED',
})

ROUTING_STATUSES = frozenset({
    'ROUTED', 'VACANCY_URL_MISSING', 'VACANCY_NOT_FOUND', 'VACANCY_MISMATCH_SUSPECTED', 'NEEDS_HUMAN_REVIEW',
})

AUTOMATION_MODES = frozenset({
    'PUBLIC_READ_ONLY', 'API_ALLOWED', 'BROWSER_READ_ONLY', 'MANUAL_INTERACTION',
    'HIGH_RISK_OR_RESTRICTED', 'UNKNOWN',
})

# Default automation mode for every Stage 5B routing record. Stage 5B never
# submits or fills anything -- the human always does the actual application
# interaction, so MANUAL_INTERACTION is the only mode used here. Independent
# of ats_provider by design (see Step 9 of the task instruction).
DEFAULT_AUTOMATION_MODE = 'MANUAL_INTERACTION'

# Primary ATS-provider signal: the connector-set label already stored,
# deterministically, in every provenance record at discovery time. This is
# never guessed -- it is the same string the real Stage 4 connector wrote.
_PRIMARY_SOURCE_TO_PROVIDER = {
    'Lever Public API': 'LEVER',
    'Greenhouse Public API': 'GREENHOUSE',
    'Ashby Public API': 'ASHBY',
}

# Fallback signal, used ONLY when primary_source is missing/unrecognized.
# Covers both observed Greenhouse domains.
_HOSTNAME_TO_PROVIDER = {
    'jobs.lever.co': 'LEVER',
    'boards.greenhouse.io': 'GREENHOUSE',
    'job-boards.greenhouse.io': 'GREENHOUSE',
    'jobs.ashbyhq.com': 'ASHBY',
}


def _distinct(values) -> list:
    seen: list = []
    for value in values:
        if value is not None and value not in seen:
            seen.append(value)
    return seen


def _derive_ats_provider(provenance: dict, job: dict) -> str:
    primary_source = provenance.get('primary_source')
    if primary_source in _PRIMARY_SOURCE_TO_PROVIDER:
        return _PRIMARY_SOURCE_TO_PROVIDER[primary_source]

    candidates: list[str] = []
    candidates.extend(provenance.get('application_urls') or [])
    candidates.extend(provenance.get('source_urls') or [])
    if job.get('Source_URL'):
        candidates.append(job['Source_URL'])
    for url in candidates:
        try:
            hostname = urlparse(url).hostname or ''
        except ValueError:
            continue
        if hostname in _HOSTNAME_TO_PROVIDER:
            return _HOSTNAME_TO_PROVIDER[hostname]
    return 'UNKNOWN'


def _select_application_url(application_urls: list[str] | None) -> tuple[str | None, str]:
    """Step 3: application URL selection.

    Returns (application_url, routing_status). Never blindly takes index 0
    when more than one URL is present without checking equivalence first.
    """
    urls = [u for u in (application_urls or []) if u]
    if not urls:
        return None, 'VACANCY_URL_MISSING'
    if len(urls) == 1:
        return urls[0], 'ROUTED'
    # More than one URL: normalize only a trivial difference (trailing slash).
    normalized = _distinct(u.rstrip('/') for u in urls)
    if len(normalized) == 1:
        # All URLs are equivalent once the trivial difference is removed --
        # choose deterministically (first, in the stored/stable order).
        return urls[0], 'ROUTED'
    # Materially different URLs. Do not silently select the first.
    return None, 'NEEDS_HUMAN_REVIEW'


def build_routing_record(job: dict, provenance: dict) -> dict:
    """Pure, deterministic Stage 5B routing-record builder.

    Performs zero network access and reads no system clock. Uses only
    already-stored Stage 4 job + provenance evidence. Identical inputs
    always produce a byte-identical output dict.
    """
    application_urls = list(provenance.get('application_urls') or [])
    application_url, routing_status = _select_application_url(application_urls)

    source_records = provenance.get('source_records') or []
    source_job_ids = _distinct(record.get('source_job_id') for record in source_records)
    requisition_ids = _distinct(record.get('requisition_id') for record in source_records)

    source_job_id = source_job_ids[0] if source_job_ids else None
    requisition_id = requisition_ids[0] if requisition_ids else None

    routing_evidence = {
        'primary_source': provenance.get('primary_source'),
        'source_job_id': source_job_id,
        'requisition_id': requisition_id,
        'matched_on': [],
        'source_urls': list(provenance.get('source_urls') or []),
        'application_urls_observed': application_urls,
    }

    # Defensive, not speculative: vacancy identity (Step 5) is anchored on a
    # single source_job_id. If provenance ever disagrees with itself about
    # what that ID is, that undermines routing just as much as an ambiguous
    # URL does, so treat it the same way -- unless the URL is already missing,
    # which is the more fundamental problem.
    if len(source_job_ids) > 1:
        routing_evidence['anomaly'] = (
            f'Multiple distinct source_job_id values observed in provenance.source_records: {source_job_ids}'
        )
        if routing_status != 'VACANCY_URL_MISSING':
            routing_status = 'NEEDS_HUMAN_REVIEW'

    return {
        'Job_ID': job.get('Job_ID'),
        'application_url': application_url,
        'ats_provider': _derive_ats_provider(provenance, job),
        'verification_status': 'NOT_YET_VERIFIED',
        'routing_status': routing_status,
        'automation_mode': DEFAULT_AUTOMATION_MODE,
        'verification_timestamp': None,
        'verification_method': None,
        'routing_evidence': routing_evidence,
    }
