from __future__ import annotations

from .base_connector import BaseJobConnector, html_to_text


class GreenhousePublicConnector(BaseJobConnector):
    connector_name = 'greenhouse'

    @property
    def discovery_url(self) -> str:
        return f'https://boards-api.greenhouse.io/v1/boards/{self.board}/jobs?content=true'

    def discover(self) -> list[dict]:
        payload = self._fetch_json(self.discovery_url)
        jobs = payload.get('jobs') if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            raise ValueError('Greenhouse board response must contain a jobs list.')
        return jobs

    def extract_source_fields(self, source_job: dict) -> dict:
        metadata = source_job.get('metadata') or []
        employment = next((item.get('value') for item in metadata if str(item.get('name', '')).lower() in {'time type', 'employment type'}), None)
        departments = source_job.get('departments') or []
        return {
            'source': 'Greenhouse Public API',
            'source_job_id': source_job.get('id'),
            'source_url': source_job.get('absolute_url'),
            'requisition_id': source_job.get('requisition_id') or source_job.get('internal_job_id'),
            'company': (source_job.get('company_name') or self.company).strip(),
            'job_title': source_job.get('title'),
            'location_raw': (source_job.get('location') or {}).get('name'),
            'posting_date_raw': source_job.get('first_published'),
            'employment_type_raw': employment,
            'seniority_raw': None,
            'department_raw': ', '.join(item.get('name', '') for item in departments if item.get('name')) or None,
            'job_description_raw': html_to_text(source_job.get('content')),
            'job_description_html_raw': source_job.get('content'),
            'application_link_raw': source_job.get('absolute_url'),
        }

    def normalize_source_metadata(self, source_job: dict) -> dict:
        return {
            'board': self.board,
            'internal_job_id': source_job.get('internal_job_id'),
            'updated_at': source_job.get('updated_at'),
            'offices': source_job.get('offices') or [],
            'metadata': source_job.get('metadata') or [],
        }

