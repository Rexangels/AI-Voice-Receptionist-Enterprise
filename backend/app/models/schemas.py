from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class DirectBookRequest:
    workflow_run_id: str
    firstName: str
    phone: str
    serviceType: str
    requestedTime: str
    tenant_id: str = "default_clinic"
    resource_id: str = "chair_1"
    verbalConfirmationConfirmed: bool = True


@dataclass
class WarmTransferBriefingRequest:
    caller_name: str
    caller_phone: str
    urgency_reason: str
    verified_details: str = "Standard intake completed"
