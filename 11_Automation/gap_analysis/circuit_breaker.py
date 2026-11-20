from __future__ import annotations


def evaluate_circuit_breaker(gaps: list[dict]) -> dict:
    records = []
    triggered = False
    for gap in gaps:
        criticality = gap.get('Criticality', 'NON_CRITICAL')
        gap_status = gap.get('Category')
        should_trigger = criticality == 'CRITICAL' and gap_status == 'MISSING'
        if should_trigger:
            triggered = True
        records.append({
            'requirement': gap.get('Requirement'),
            'evidence': gap.get('Evidence'),
            'gap_status': gap_status,
            'criticality': criticality,
            'circuit_breaker_triggered': should_trigger,
            'reason': (
                'Confirmed missing critical requirement.' if should_trigger
                else 'Circuit breaker requires both CRITICAL and confirmed MISSING.'
            ),
            'source': gap.get('Source'),
        })
    return {
        'Status': 'TRIGGERED' if triggered else 'CLEAR',
        'Triggered': triggered,
        'Records': records,
    }
