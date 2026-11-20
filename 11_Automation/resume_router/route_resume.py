from __future__ import annotations

import re

from common import BASE_RESUMES, FUNCTIONAL_ROUTES


ROUTING_TERMS = {
    'Commercial / Research': {
        'strategy': 5, 'business strategy': 6, 'corporate strategy': 6,
        'commercial strategy': 5, 'market intelligence': 6, 'competitive intelligence': 6,
        'competitor': 3, 'market research': 5, 'growth': 3, 'business planning': 4,
        'strategic planning': 5, 'management associate': 3, 'business analytics': 5,
        'data analyst': 5, 'business intelligence': 5, 'analytics': 3, 'insights': 4,
        'operations analyst': 4, 'reporting analyst': 4, 'performance analyst': 4,
        'customer insights': 5, 'marketing analytics': 5, 'dashboard': 3, 'sql': 3,
        'data analysis': 4, 'digital transformation': 4, 'ai transformation': 4,
        'business process': 3, 'automation analyst': 3, 'business development': 3,
        'commercial projects': 4, 'content': 2,
    },
    'Corporate Finance / Transaction / Advisory': {
        'financial analyst': 7, 'finance analyst': 7, 'fp&a': 7, 'commercial finance': 6,
        'corporate finance': 7, 'valuation': 5, 'dcf': 5, 'wacc': 5, 'treasury': 5,
        'management reporting': 4, 'financial reporting': 5, 'financial planning': 5,
        'budgeting': 4, 'forecasting': 4, 'investment analysis': 4, 'credit risk': 5,
        'credit analyst': 6, 'risk analyst': 5, 'operational risk': 5, 'banking': 4,
        'corporate banking': 6, 'commercial banking': 6, 'transaction banking': 6,
        'client service': 2, 'kyc': 4, 'aml': 4, 'financial crime': 4,
        'fraud risk': 4, 'due diligence': 4, 'credit': 3, 'advisory': 4,
        'capital raising': 4, 'financing': 5,
    },
    'Markets / FMI / FinTech': {
        'capital markets': 7, 'financial markets': 7, 'equity research': 6,
        'fixed income': 6, 'asset management': 5, 'investment analyst': 5,
        'investment research': 5, 'trading': 6, 'derivatives': 5, 'securities': 5,
        'market infrastructure': 7, 'clearing': 6, 'settlement': 6, 'exchange': 4,
        'fintech': 6, 'financial technology': 6, 'payments': 5, 'middle office': 5,
        'quant': 5, 'portfolio': 4, 'liquidity': 4, 'risk analytics': 4,
    },
}


BASE_SELECTION_TERMS = {
    'COMMERCIAL_PRIMARY': {
        'strategy': 4, 'market intelligence': 5, 'competitive intelligence': 5,
        'market research': 5, 'competitor': 3, 'business analytics': 4,
        'data analyst': 4, 'analytics': 3, 'insights': 4, 'customer': 2,
        'marketing': 4, 'growth': 3, 'business development': 3,
        'commercial projects': 4, 'operations': 2, 'digital transformation': 3,
        'research': 2,
    },
    'CF_TRANSACTION_SECONDARY': {
        'finance': 4, 'financial': 4, 'fp&a': 6, 'corporate finance': 6,
        'transaction': 5, 'advisory': 5, 'banking': 5, 'credit': 4, 'risk': 3,
        'valuation': 5, 'treasury': 4, 'investment': 4, 'capital markets': 5,
        'fixed income': 4, 'bond': 4, 'loan': 4, 'financing': 5,
        'due diligence': 4, 'middle office': 4, 'payments': 3, 'portfolio': 3,
    },
}


TITLE_ROUTE = {
    'Credit Analyst': 'Corporate Finance / Transaction / Advisory',
    'Operational Risk Analyst': 'Corporate Finance / Transaction / Advisory',
    'Corporate Banking Analyst': 'Corporate Finance / Transaction / Advisory',
    'KYC / AML Analyst': 'Corporate Finance / Transaction / Advisory',
    'Financial Analyst': 'Corporate Finance / Transaction / Advisory',
    'Commercial Finance Analyst': 'Corporate Finance / Transaction / Advisory',
    'Valuation Analyst': 'Corporate Finance / Transaction / Advisory',
    'Strategy Analyst': 'Commercial / Research',
    'Market Intelligence Analyst': 'Commercial / Research',
    'Business Analytics Analyst': 'Commercial / Research',
    'Operations Analyst': 'Commercial / Research',
    'AI Transformation Analyst': 'Commercial / Research',
    'AI Business Analyst': 'Commercial / Research',
    'Automation Analyst': 'Commercial / Research',
}


ENGINEERING_PATTERNS = [
    r'\bsoftware engineer\b', r'\bmachine learning engineer\b', r'\bml engineer\b',
    r'\bbackend engineer\b', r'\bdeep learning deployment\b', r'\bproduction ml\b',
]


def _job_text(job: dict) -> str:
    return ' '.join([
        job.get('Role_Title') or '', job.get('Normalized_Role_Title') or '',
        job.get('Business_Function') or '', job.get('Industry') or '',
        job.get('Job_Description_Clean') or '', ' '.join(job.get('Responsibilities') or []),
        ' '.join(job.get('Required_Skills') or []), ' '.join(job.get('Preferred_Skills') or []),
    ]).lower()


def _score_terms(text: str, terms_by_bucket: dict[str, dict[str, int]]) -> dict[str, int]:
    scores = {bucket: 0 for bucket in terms_by_bucket}
    for bucket, terms in terms_by_bucket.items():
        for term, weight in terms.items():
            if term in text:
                scores[bucket] += weight
    return scores


def is_incompatible_engineering(job: dict) -> bool:
    return any(re.search(pattern, _job_text(job)) for pattern in ENGINEERING_PATTERNS)


def _empty_route(reason: str, human_review: bool) -> dict:
    return {
        'Primary_Route': None,
        'Secondary_Route': None,
        'Primary_Resume': None,
        'Primary_Reason': reason,
        'Optional_Secondary_Resume': None,
        'Secondary_Reason': None,
        'Secondary_Allowed': False,
        'Routing_Confidence': 'LOW' if human_review else 'HIGH',
        'Human_Review_Required': human_review,
        'Recommended_Resume': None,
        'Route_Scores': {route: 0 for route in FUNCTIONAL_ROUTES},
        'Base_Scores': {base: 0 for base in BASE_RESUMES},
        'Reason': reason,
    }


def route_resume(job: dict) -> dict:
    if is_incompatible_engineering(job):
        return _empty_route('Fundamentally incompatible pure software/ML engineering role.', False)

    text = _job_text(job)
    route_scores = _score_terms(text, ROUTING_TERMS)
    base_scores = _score_terms(text, BASE_SELECTION_TERMS)

    normalized_title = job.get('Normalized_Role_Title')
    if normalized_title in TITLE_ROUTE:
        title_bonus = 14 if normalized_title == 'Commercial Finance Analyst' else 8
        route_scores[TITLE_ROUTE[normalized_title]] += title_bonus
    if normalized_title == 'Business Analyst':
        route_scores['Commercial / Research'] += 5
        route_scores['Markets / FMI / FinTech'] += 1

    ranked_routes = sorted(
        route_scores.items(), key=lambda item: (-item[1], FUNCTIONAL_ROUTES.index(item[0]))
    )
    primary_route, top_route_score = ranked_routes[0]
    secondary_route, second_route_score = ranked_routes[1]
    if top_route_score == 0:
        return _empty_route('Insufficient functional evidence for deterministic route or base selection.', True)

    if primary_route == 'Commercial / Research':
        base_scores['COMMERCIAL_PRIMARY'] += 4
    elif primary_route == 'Corporate Finance / Transaction / Advisory':
        base_scores['CF_TRANSACTION_SECONDARY'] += 4

    ranked_bases = sorted(
        base_scores.items(), key=lambda item: (-item[1], BASE_RESUMES.index(item[0]))
    )
    primary_base, top_base_score = ranked_bases[0]
    secondary_base, second_base_score = ranked_bases[1]

    # A selective Markets/FMI/FinTech route chooses the nearest evidence base.
    # A scoreless tie defaults conservatively to CF / Transaction because the
    # production evidence includes banking, financing, valuation, and markets analysis.
    if top_base_score == 0 and primary_route == 'Markets / FMI / FinTech':
        primary_base = 'CF_TRANSACTION_SECONDARY'
        base_scores[primary_base] = 1
        top_base_score = 1
        secondary_base = 'COMMERCIAL_PRIMARY'
        second_base_score = 0

    secondary_route_value = (
        secondary_route if second_route_score >= 4 and top_route_score - second_route_score <= 5 else None
    )
    optional_secondary_base = (
        secondary_base if second_base_score >= 4 and top_base_score - second_base_score <= 4 else None
    )

    route_margin = top_route_score - second_route_score
    base_margin = top_base_score - second_base_score
    confidence = (
        'HIGH' if top_route_score >= 12 and route_margin >= 5 and base_margin >= 3
        else ('MEDIUM' if top_route_score >= 7 and top_base_score > 0 else 'LOW')
    )
    primary_reason = (
        f'{primary_route} led functional evidence with {top_route_score} points; '
        f'{primary_base} was the nearest governed evidence base with {top_base_score} points.'
    )
    secondary_reason = (
        f'{optional_secondary_base} remains an optional alternative evidence base with '
        f'{second_base_score} points; bases are never merged.'
        if optional_secondary_base else None
    )

    return {
        'Primary_Route': primary_route,
        'Secondary_Route': secondary_route_value,
        'Primary_Resume': primary_base,
        'Primary_Reason': primary_reason,
        'Optional_Secondary_Resume': optional_secondary_base,
        'Secondary_Reason': secondary_reason,
        'Secondary_Allowed': optional_secondary_base is not None,
        'Routing_Confidence': confidence,
        'Human_Review_Required': confidence == 'LOW',
        'Recommended_Resume': primary_base,
        'Route_Scores': route_scores,
        'Base_Scores': base_scores,
        'Reason': (
            f'{primary_route} led the functional classification by {route_margin} points; '
            f'{primary_base} led base selection by {base_margin} points.'
        ),
    }
