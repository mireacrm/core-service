"""Представления домена в HTTP-ответах. Аналог `rpc/mapping.py` для gRPC."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import EmployeeRole


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    inn: str
    created_at: datetime


class BranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    address: str
    timezone: str


class ShiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    starts_at: datetime
    ends_at: datetime


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    full_name: str
    role: EmployeeRole
    is_active: bool


class ScheduleOut(BaseModel):
    employee: EmployeeOut
    shifts: list[ShiftOut]


class EmployeeIdentityOut(BaseModel):
    """Кем является учётная запись. Служебный ответ для шлюза."""

    model_config = ConfigDict(from_attributes=True)

    employee_id: uuid.UUID
    branch_id: uuid.UUID
    role: EmployeeRole
