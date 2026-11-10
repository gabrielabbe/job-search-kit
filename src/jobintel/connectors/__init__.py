from .ashby import AshbyConnector
from .base import Connector
from .greenhouse import GreenhouseConnector
from .lever import LeverConnector
from .smartrecruiters import SmartRecruitersConnector

CONNECTORS = {
    "greenhouse": GreenhouseConnector,
    "lever": LeverConnector,
    "ashby": AshbyConnector,
    "smartrecruiters": SmartRecruitersConnector,
}

__all__ = ["CONNECTORS", "Connector", "GreenhouseConnector", "LeverConnector", "AshbyConnector",
           "SmartRecruitersConnector"]
