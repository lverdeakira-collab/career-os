"""Singapore employment-policy and job-language evaluation."""

from .evaluate_policy import evaluate_singapore_employment_policy
from .language_classifier import classify_language_requirements
from .work_authorization import classify_work_authorization

__all__ = [
    'classify_language_requirements',
    'classify_work_authorization',
    'evaluate_singapore_employment_policy',
]
