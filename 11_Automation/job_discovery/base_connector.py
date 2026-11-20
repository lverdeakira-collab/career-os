from __future__ import annotations

from abc import ABC, abstractmethod
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class _TextExtractor(HTMLParser):
    BLOCKS = {'p', 'div', 'li', 'ul', 'ol', 'h1', 'h2', 'h3', 'h4', 'br'}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.BLOCKS and self.parts and self.parts[-1] != '\n':
            self.parts.append('\n')

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.BLOCKS:
            self.parts.append('\n')

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


def html_to_text(value: str | None) -> str:
    parser = _TextExtractor()
    parser.feed(unescape(value or ''))
    lines = [' '.join(line.split()) for line in ''.join(parser.parts).splitlines()]
    return '\n'.join(line for line in lines if line)


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


class SourceAccessError(RuntimeError):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


class BaseJobConnector(ABC):
    connector_name = 'base'
    source_category = 'Public ATS job pages'

    def __init__(self, board: str, company: str, timeout: int = 20) -> None:
        self.board = board
        self.company = company
        self.timeout = timeout

    @property
    @abstractmethod
    def discovery_url(self) -> str:
        raise NotImplementedError

    def _fetch_json(self, url: str) -> Any:
        request = Request(url, headers={'User-Agent': 'Career_OS-Stage4/0.1 (public-job-validation)'})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise SourceAccessError('SOURCE_ACCESS_LIMITED', f'HTTP {response.status} for {url}')
                return json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            raise SourceAccessError('SOURCE_ACCESS_LIMITED', f'HTTP {exc.code} for {url}') from exc
        except (URLError, TimeoutError) as exc:
            raise SourceAccessError('SOURCE_ACCESS_LIMITED', f'Access failed for {url}: {exc}') from exc
        except json.JSONDecodeError as exc:
            raise SourceAccessError('PARSING_ERROR', f'Invalid JSON from {url}') from exc

    @abstractmethod
    def discover(self) -> list[dict]:
        raise NotImplementedError

    def fetch_job(self, source_job_id: str) -> dict | None:
        return next((job for job in self.discover() if str(job.get('id')) == str(source_job_id)), None)

    @abstractmethod
    def extract_source_fields(self, source_job: dict) -> dict:
        raise NotImplementedError

    @abstractmethod
    def normalize_source_metadata(self, source_job: dict) -> dict:
        raise NotImplementedError

    def make_raw_record(self, source_job: dict, run_id: str, retrieved_at: str, *, replay: bool = False) -> dict:
        fields = self.extract_source_fields(source_job)
        source_job_id = str(fields['source_job_id'])
        suffix = '-REPLAY' if replay else ''
        payload_text = stable_json(source_job)
        return {
            'schema_version': '0.1',
            'raw_record_id': f'RAW-{run_id}-{self.connector_name.upper()}-{source_job_id}{suffix}',
            'run_id': run_id,
            'source_connector': self.connector_name,
            'source_category': self.source_category,
            'source': fields['source'],
            'source_url': fields['source_url'],
            'source_api_url': self.discovery_url,
            'source_job_id': source_job_id,
            'requisition_id': fields.get('requisition_id'),
            'company': fields['company'],
            'job_title': fields['job_title'],
            'location_raw': fields.get('location_raw'),
            'posting_date_raw': fields.get('posting_date_raw'),
            'employment_type_raw': fields.get('employment_type_raw'),
            'seniority_raw': fields.get('seniority_raw'),
            'department_raw': fields.get('department_raw'),
            'job_description_raw': fields.get('job_description_raw') or '',
            'job_description_html_raw': fields.get('job_description_html_raw'),
            'application_link_raw': fields.get('application_link_raw'),
            'retrieved_at': retrieved_at,
            'source_metadata': self.normalize_source_metadata(source_job),
            'source_payload_sha256': sha256(payload_text.encode('utf-8')).hexdigest(),
            'source_payload': source_job,
            'retrieval_status': 'SUCCESS',
            'validation_replay': replay,
        }
