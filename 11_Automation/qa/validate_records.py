from __future__ import annotations


def validate_unique_ids(records: list[dict], id_field: str) -> list[str]:
    values = [record.get(id_field) for record in records]
    errors = []
    if any(not value for value in values):
        errors.append(f'{id_field} must be populated for every persisted record.')
    duplicates = sorted({value for value in values if value and values.count(value) > 1})
    if duplicates:
        errors.append(f'Duplicate {id_field} values: {duplicates}')
    return errors


def validate_one_application_per_job(applications: list[dict]) -> list[str]:
    job_ids = [record.get('Job_ID') for record in applications]
    duplicates = sorted({value for value in job_ids if value and job_ids.count(value) > 1})
    return [f'Multiple applications linked to one Job_ID: {duplicates}'] if duplicates else []


def validate_status(record: dict, field: str, allowed: list[str]) -> list[str]:
    return [] if record.get(field) in allowed else [f'Invalid {field}: {record.get(field)!r}']
