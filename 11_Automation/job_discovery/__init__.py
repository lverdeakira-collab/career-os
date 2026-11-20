"""Career_OS Stage 4 public job-discovery connectors."""

from .ashby_connector import AshbyPublicConnector
from .greenhouse_connector import GreenhousePublicConnector
from .lever_connector import LeverPublicConnector

CONNECTOR_TYPES = {
    'ashby': AshbyPublicConnector,
    'greenhouse': GreenhousePublicConnector,
    'lever': LeverPublicConnector,
}
