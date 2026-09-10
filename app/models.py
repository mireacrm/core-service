import enum
import uuid
from collections.abc import Iterable
from datetime import datetime
from itertools import pairwise
from typing import Annotated

from mireacrm_common.errors import ConflictError
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class EmployeeRole(enum.StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    SPECIALIST = "specialist"


UuidPk = Annotated[
    uuid.UUID, mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
]
CreatedAt = Annotated[
    datetime, mapped_column(DateTime(timezone=True), server_default=func.now())
]


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[UuidPk]
    name: Mapped[str] = mapped_column(String(200))
    inn: Mapped[str] = mapped_column(String(12), unique=True)
    created_at: Mapped[CreatedAt]

    branches: Mapped[list["Branch"]] = relationship(back_populates="company")


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[UuidPk]
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    created_at: Mapped[CreatedAt]

    company: Mapped[Company] = relationship(back_populates="branches")
    employees: Mapped[list["Employee"]] = relationship(back_populates="branch")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[UuidPk]
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"))
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[EmployeeRole] = mapped_column(Enum(EmployeeRole, name="employee_role"))
    # Учётная запись, которой соответствует сотрудник. Может отсутствовать:
    # не у каждого сотрудника есть доступ в систему.
    keycloak_subject: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[CreatedAt]

    branch: Mapped[Branch] = relationship(back_populates="employees")
    shifts: Mapped[list["WorkShift"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )

    def assign_shifts(self, periods: Iterable[tuple[datetime, datetime]]) -> None:
        ordered = sorted(periods)
        for (_, prev_end), (next_start, _) in pairwise(ordered):
            if next_start < prev_end:
                raise ConflictError(
                    f"смены пересекаются: {prev_end.isoformat()} и {next_start.isoformat()}"
                )
        self.shifts = [WorkShift(starts_at=s, ends_at=e) for s, e in ordered]


class WorkShift(Base):
    __tablename__ = "work_shifts"

    id: Mapped[UuidPk]
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    employee: Mapped[Employee] = relationship(back_populates="shifts")
