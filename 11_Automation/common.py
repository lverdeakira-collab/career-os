from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


AUTOMATION_ROOT = Path(__file__).resolve().parent
CAREER_OS_ROOT = AUTOMATION_ROOT.parent
ENGINE_ROOT = CAREER_OS_ROOT / '15_Application_Engine'

FUNCTIONAL_ROUTES = [
    'Commercial / Research',
    'Corporate Finance / Transaction / Advisory',
    'Markets / FMI / FinTech',
]

BASE_RESUMES = [
    'COMMERCIAL_PRIMARY',
    'CF_TRANSACTION_SECONDARY',
]

# Backward-compatible alias for modules that reason about functional routes.
# Base-resume selection must use BASE_RESUMES, not DIRECTIONS.
DIRECTIONS = FUNCTIONAL_ROUTES

RESUME_PATHS = {
    'COMMERCIAL_PRIMARY': '16_Resume_Rebuild/production_base_cuts/commercial_primary_base_cut.pdf',
    'CF_TRANSACTION_SECONDARY': '16_Resume_Rebuild/production_base_cuts/cf_transaction_secondary_base_cut.pdf',
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def clean_space(value: str | None) -> str:
    return re.sub(r'\s+', ' ', value or '').strip()


def slug(value: str, fallback: str = 'UNKNOWN') -> str:
    cleaned = re.sub(r'[^A-Za-z0-9]+', '', value or '').upper()
    return cleaned or fallback


def normalized_terms(value: str) -> set[str]:
    return set(re.findall(r'[a-z0-9+#]+', value.lower()))
