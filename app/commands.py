"""Входные команды предметной области.

Домен принимает их и от REST, и от gRPC. Выходные представления у каждого
транспорта свои: `api/schemas.py` для HTTP, `rpc/mapping.py` для gRPC.
"""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models import EmployeeRole


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    inn: str = Field(pattern=r"^\d{10}$|^\d{12}$")


class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=500)
    timezone: str = "Europe/Moscow"


class ShiftIn(BaseModel):
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def check_order(self) -> "ShiftIn":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at должен быть позже starts_at")
        return self


class EmployeeCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    role: EmployeeRole
    # Учётная запись в системе управления доступом, если она у сотрудника есть.
    keycloak_subject: str = Field(default="", max_length=64)
    shifts: list[ShiftIn] = Field(default_factory=list)
