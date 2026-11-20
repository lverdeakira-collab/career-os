from __future__ import annotations

from .base_connector import BaseJobConnector, html_to_text


class LeverPublicConnector(BaseJobConnector):
    connector_name = 'lever'

    @property
    def discovery_url(self) -> str:
        return f'https://api.lever.co/v0/postings/{self.board}?mode=json'

    def discover(self) -> list[dict]:
        payload = self._fetch_json(self.discovery_url)
        if not isinstance(payload, list):
            raise ValueError('Lever board response must be a list.')
        return payload

    def extract_source_fields(self, source_job: dict) -> dict:
        categories = source_job.get('categories') or {}
        sections = [source_job.get('openingPlain') or source_job.get('descriptionPlain') or '']
        for item in source_job.get('lists') or []:
            sections.extend([item.get('text') or '', html_to_text(item.get('content'))])
        sections.append(source_job.get('additionalPlain') or '')
        complete_plain = '\n\n'.join(part.strip() for part in sections if part and part.strip())
        return {
            'source': 'Lever Public API',
            'source_job_id': source_job.get('id'),
            'source_url': source_job.get('hostedUrl'),
            'requisition_id': None,
            'company': self.company,
            'job_title': source_job.get('text'),
            'location_raw': categories.get('location'),
            'posting_date_raw': source_job.get('createdAt'),
            'employment_type_raw': categories.get('commitment'),
            'seniority_raw': None,
            'department_raw': categories.get('department') or categories.get('team'),
            'job_description_raw': complete_plain,
            'job_description_html_raw': source_job.get('opening') or source_job.get('description'),
            'application_link_raw': source_job.get('applyUrl'),
        }

    def normalize_source_metadata(self, source_job: dict) -> dict:
        return {
            'board': self.board,
            'workplace_type': source_job.get('workplaceType'),
            'country_code': source_job.get('country'),
            'categories': source_job.get('categories') or {},
        }

