"""Request and response models of the shared-device routes.

`routers/v1/device_enrolment.py` serves them. Nothing here ever carries a
device's secret: the register request is the only model that holds one, and no
response does.
"""

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EnrolmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization: str = Field(min_length=1, max_length=255, description="Organization slug")
    label: str = Field(min_length=1, max_length=100, description="Shown to the approver as sent")
    secret: str = Field(
        min_length=43,
        max_length=64,
        description="32 random bytes the device generated: 64 hex chars or 43 base64url chars",
    )
    template: Optional[str] = Field(default=None, max_length=64)
    device_client_id: Optional[str] = Field(
        default=None, max_length=255, description="Set when re-enrolling an existing device"
    )

    @field_validator("label")
    @classmethod
    def _printable_label(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned or not cleaned.isprintable():
            raise ValueError("label must be printable text")
        return cleaned


class EnrolmentCreated(BaseModel):
    enrolment_id: uuid.UUID
    status: Literal["pending"]
    user_code: str
    expires_at: datetime
    poll_interval_seconds: int


class EnrolmentStatus(BaseModel):
    enrolment_id: uuid.UUID
    status: Literal["pending", "approved", "expired"]
    expires_at: datetime
    client_id: Optional[str] = None


class ReplacedDevice(BaseModel):
    id: uuid.UUID
    client_id: Optional[str]
    label: str


class PendingEnrolment(BaseModel):
    id: uuid.UUID
    user_code: str
    label: str
    label_is_unverified: bool = True
    template: str
    requested_at: datetime
    expires_at: datetime
    requested_from: Optional[str]
    requested_user_agent: Optional[str]
    replaces_device: Optional[ReplacedDevice]


class PendingEnrolmentList(BaseModel):
    data: list[PendingEnrolment]


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_code: str = Field(min_length=8, max_length=16)


class DeviceView(BaseModel):
    id: uuid.UUID
    client_id: Optional[str]
    label: str
    template: str
    status: str
    approved_by: Optional[uuid.UUID]
    approved_at: datetime
    disabled_by: Optional[uuid.UUID]
    disabled_at: Optional[datetime]
    disabled_reason: Optional[str]
    last_token_at: Optional[datetime]
    clone_suspected_at: Optional[datetime]
    boot_alternations: int
    created_at: datetime


class DeviceList(BaseModel):
    data: list[DeviceView]


class ApproveResponse(BaseModel):
    re_enrolment: bool
    device: DeviceView


class DisableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Optional[str] = Field(default=None, max_length=300)


class DisableResponse(BaseModel):
    changed: bool
    device: DeviceView
