from __future__ import annotations

from .base_connector import BaseJobConnector


class AshbyPublicConnector(BaseJobConnector):
    connector_name = 'ashby'

    @property
    def discovery_url(self) -> str:
        return f'https://api.ashbyhq.com/posting-api/job-board/{self.board}'

    def discover(self) -> list[dict]:
        payload = self._fetch_json(self.discovery_url)
        jobs = payload.get('jobs') if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            raise ValueError('Ashby board response must contain a jobs list.')
        return jobs

    def extract_source_fields(self, source_job: dict) -> dict:
        return {
            'source': 'Ashby Public API',
            'source_job_id': source_job.get('id'),
            'source_url': source_job.get('jobUrl'),
            'requisition_id': None,
            'company': self.company,
            'job_title': source_job.get('title'),
            'location_raw': source_job.get('location'),
            'posting_date_raw': source_job.get('publishedAt'),
            'employment_type_raw': source_job.get('employmentType'),
            'seniority_raw': None,
            'department_raw': source_job.get('department') or source_job.get('team'),
            'job_description_raw': source_job.get('descriptionPlain') or '',
            'job_description_html_raw': source_job.get('descriptionHtml'),
            'application_link_raw': source_job.get('applyUrl'),
        }

    def normalize_source_metadata(self, source_job: dict) -> dict:
        return {
            'board': self.board,
            'workplace_type': source_job.get('workplaceType'),
            'is_remote': source_job.get('isRemote'),
            'is_listed': source_job.get('isListed'),
            'address': source_job.get('address'),
            'secondary_locations': source_job.get('secondaryLocations') or [],
        }
