"""User-configurable eligibility rules (work authorization and languages).

Nothing in this package is tied to a country or a government policy. The
candidate states their own facts in the Candidate Profile, and chooses in the
Candidate Strategy how each kind of posting restriction should be handled.
"""

from .language_classifier import classify_language_requirements
from .preferences import ACTIONS, DEFAULT_PREFERENCES, load_preferences
from .work_authorization import classify_work_authorization

__all__ = [
    'ACTIONS',
    'DEFAULT_PREFERENCES',
    'classify_language_requirements',
    'classify_work_authorization',
    'load_preferences',
]
