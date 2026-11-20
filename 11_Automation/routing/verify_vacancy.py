from __future__ import annotations

from datetime import datetime, timezone
import re


VERIFICATION_METHOD_SOURCE_API_REPOLL = 'SOURCE_API_REPOLL'

_PROVIDER_TO_CONNECTOR_TYPE = {
    'LEVER': 'lever',
    'GREENHOUSE': 'greenhouse',
    'ASHBY': 'ashby',
}

# Inverse of each connector's own `discovery_url` property (see
# 11_Automation/job_discovery/{lever,greenhouse,ashby}_connector.py). Used to
# recover the board name from the provenance record's own stored
# source_api_url, without needing a second config file or duplicating the
# connector's URL-building logic.
_BOARD_PATTERNS = {
    'lever': re.compile(r'^https://api\.lever\.co/v0/postings/([^?]+)'),
    'greenhouse': re.compile(r'^https://boards-api\.greenhouse\.io/v1/boards/([^/]+)/jobs'),
    'ashby': re.compile(r'^https://api\.ashbyhq\.com/posting-api/job-board/([^/?]+)'),
}

_PUNCTUATION_RE = re.compile(r'[.,\'"\-–—()&]')
_WHITESPACE_RE = re.compile(r'\s+')


def _normalize_text(value) -> str | None:
    """Conservative normalization only: case, whitespace, minor punctuation.
    Not a fuzzy-matching framework (Step 7)."""
    if value is None:
        return None
    text = _PUNCTUATION_RE.sub(' ', str(value).lower())
    return _WHITESPACE_RE.sub(' ', text).strip()


def _parse_board(connector_type: str, source_api_url: str | None) -> str | None:
    pattern = _BOARD_PATTERNS.get(connector_type)
    if not pattern or not source_api_url:
        return None
    match = pattern.match(source_api_url)
    return match.group(1) if match else None


def _result(routing_evidence: dict, *, verification_status: str, routing_status: str,
            timestamp: str, matched_on: list[str] | None = None, note: str | None = None) -> dict:
    evidence = dict(routing_evidence)
    if matched_on is not None:
        evidence['matched_on'] = matched_on
    if note is not None:
        evidence['verification_note'] = note
    return {
        'verification_status': verification_status,
        'routing_status': routing_status,
        'verification_timestamp': timestamp,
        'verification_method': VERIFICATION_METHOD_SOURCE_API_REPOLL,
        'routing_evidence': evidence,
    }


def verify_vacancy(job: dict, provenance: dict, routing_record: dict, *,
                    connector_types: dict, now: callable | None = None) -> dict:
    """Live vacancy verification for one job (Step 6).

    Reuses the existing Stage 4 connector classes' own discover() and
    extract_source_fields() -- no connector/API logic is duplicated here.
    This is the only Stage 5B function that performs network access, and it
    is PUBLIC_READ_ONLY by construction: it calls the same unauthenticated
    public board APIs Stage 4 discovery already calls.

    `connector_types` is an injected {connector_type_key: ConnectorClass}
    mapping (production callers pass job_discovery.CONNECTOR_TYPES; tests
    inject fakes) so unit tests never need real network access.

    Returns only the fields that change: verification_status, routing_status,
    verification_timestamp, verification_method, routing_evidence. The
    caller merges these into the existing routing record.
    """
    clock = now or (lambda: datetime.now(timezone.utc))
    timestamp = clock().isoformat()
    evidence = dict(routing_record.get('routing_evidence') or {})

    if not routing_record.get('application_url'):
        # Nothing to verify against a URL-level problem; leave as-is rather
        # than fabricate a verification attempt. Not exercised by any of the
        # current 19 real jobs (all have exactly one application URL).
        return _result(
            evidence,
            verification_status=routing_record.get('verification_status', 'NOT_YET_VERIFIED'),
            routing_status=routing_record.get('routing_status', 'VACANCY_URL_MISSING'),
            timestamp=timestamp,
            note='Verification skipped: no application_url to verify against.',
        )

    ats_provider = routing_record.get('ats_provider')
    connector_type = _PROVIDER_TO_CONNECTOR_TYPE.get(ats_provider)
    if connector_type is None or connector_type not in connector_types:
        # Case: unsupported/unknown provider. A failed lookup is not evidence
        # the vacancy disappeared -- surface it as a failure needing a human,
        # never as VACANCY_NOT_FOUND.
        return _result(
            evidence,
            verification_status='VERIFICATION_FAILED',
            routing_status='NEEDS_HUMAN_REVIEW',
            timestamp=timestamp,
            note=f'No connector available for ats_provider={ats_provider!r}; cannot verify.',
        )

    source_records = provenance.get('source_records') or []
    source_api_url = next((r.get('source_api_url') for r in source_records if r.get('source_api_url')), None)
    board = _parse_board(connector_type, source_api_url)
    if board is None:
        return _result(
            evidence,
            verification_status='VERIFICATION_FAILED',
            routing_status='NEEDS_HUMAN_REVIEW',
            timestamp=timestamp,
            note='Could not determine source board from provenance.source_records[].source_api_url; cannot verify.',
        )

    historical_source_job_id = evidence.get('source_job_id')
    historical_requisition_id = evidence.get('requisition_id')

    connector = connector_types[connector_type](board, job.get('Company') or '')
    try:
        fresh_postings = connector.discover()
    except Exception as exc:  # SourceAccessError, or any other connector/network failure.
        # STEP 6 / E: a source-access failure is NEVER evidence the vacancy
        # disappeared. Preserve the known application_url; do not touch it.
        return _result(
            evidence,
            verification_status='VERIFICATION_FAILED',
            routing_status='NEEDS_HUMAN_REVIEW',
            timestamp=timestamp,
            note=f'{type(exc).__name__}: {exc}',
        )

    match = next((p for p in fresh_postings if str(p.get('id')) == str(historical_source_job_id)), None)
    if match is None:
        # STEP 6 / B: fresh call succeeded, source_job_id is genuinely absent.
        return _result(
            evidence,
            verification_status='VERIFIED_REMOVED_OR_CLOSED',
            routing_status='VACANCY_NOT_FOUND',
            timestamp=timestamp,
            note='source_job_id not present in a successful fresh discover() listing.',
        )

    fresh_fields = connector.extract_source_fields(match)
    fresh_requisition_id = fresh_fields.get('requisition_id')
    fresh_title = fresh_fields.get('job_title')
    fresh_company = fresh_fields.get('company')

    matched_on = ['source_job_id']

    # STEP 6 / C: requisition_id materially changed. Checked before title/
    # company because it is the stronger secondary identity signal (Step 5).
    # Only meaningful when a requisition_id was historically available
    # (Greenhouse only in current data -- Lever/Ashby never populate it).
    if (
        historical_requisition_id is not None
        and fresh_requisition_id is not None
        and str(fresh_requisition_id) != str(historical_requisition_id)
    ):
        return _result(
            evidence,
            verification_status='VERIFIED_ACTIVE',
            routing_status='VACANCY_MISMATCH_SUSPECTED',
            timestamp=timestamp,
            matched_on=matched_on,
            note=f'requisition_id changed: {historical_requisition_id!r} -> {fresh_requisition_id!r}.',
        )
    if historical_requisition_id is not None and fresh_requisition_id is not None:
        matched_on.append('requisition_id')

    # STEP 7: conservative title/company comparison only -- no fuzzy matching.
    # Company is a genuine corroborating signal only for Greenhouse, where the
    # connector can extract company_name from the source payload itself; for
    # Lever/Ashby, extract_source_fields()'s 'company' key is the constructor
    # argument we passed in (job['Company']), not a value read from the
    # source API, so it can never actually disagree -- documented in the
    # Stage 5B final report rather than treated as a real corroborating check.
    title_matches = _normalize_text(fresh_title) == _normalize_text(job.get('Role_Title'))
    company_signal_available = connector_type == 'greenhouse'
    company_matches = True
    if company_signal_available:
        company_matches = _normalize_text(fresh_company) == _normalize_text(job.get('Company'))

    if title_matches:
        matched_on.append('role_title')
    if company_signal_available and company_matches:
        matched_on.append('company')

    if not title_matches or (company_signal_available and not company_matches):
        # STEP 6 / D: source_job_id still matches, but title/company changed
        # beyond conservative normalization. Do NOT mark the vacancy closed.
        return _result(
            evidence,
            verification_status='VERIFIED_ACTIVE',
            routing_status='NEEDS_HUMAN_REVIEW',
            timestamp=timestamp,
            matched_on=matched_on,
            note=(
                f'source_job_id matched but title/company changed beyond conservative '
                f'normalization (fresh_title={fresh_title!r}, fresh_company={fresh_company!r}).'
            ),
        )

    # STEP 6 / A: clean match.
    return _result(
        evidence,
        verification_status='VERIFIED_ACTIVE',
        routing_status='ROUTED',
        timestamp=timestamp,
        matched_on=matched_on,
    )
