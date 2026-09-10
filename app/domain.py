"""Бизнес-операции. Используются и REST-слоем, и gRPC-сервером."""

import uuid
from datetime import UTC, datetime

from mirea.events.v1 import events_pb2
from mireacrm_common.errors import ConflictError, NotFoundError
from mireacrm_common.events import EventPublisher
from mireacrm_common.pagination import decode_cursor, encode_cursor
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import commands, models


async def create_company(session: AsyncSession, data: commands.CompanyCreate) -> models.Company:
    exists = await session.scalar(select(models.Company).where(models.Company.inn == data.inn))
    if exists is not None:
        raise ConflictError(f"компания с ИНН {data.inn} уже зарегистрирована")

    company = models.Company(name=data.name, inn=data.inn)
    session.add(company)
    await session.commit()
    await session.refresh(company)
    return company


async def open_branch(
    session: AsyncSession,
    company_id: uuid.UUID,
    data: commands.BranchCreate,
    publisher: EventPublisher,
) -> models.Branch:
    company = await session.get(models.Company, company_id)
    if company is None:
        raise NotFoundError("company", company_id)

    branch = models.Branch(
        company_id=company_id, name=data.name, address=data.address, timezone=data.timezone
    )
    session.add(branch)
    await session.commit()
    await session.refresh(branch)

    await publisher.publish(
        "branch.opened",
        branch_opened=events_pb2.BranchOpened(
            branch_id=str(branch.id), company_id=str(branch.company_id), name=branch.name
        ),
    )
    return branch


async def get_branch(session: AsyncSession, branch_id: uuid.UUID) -> models.Branch:
    branch = await session.get(models.Branch, branch_id)
    if branch is None:
        raise NotFoundError("branch", branch_id)
    return branch


async def hire_employee(
    session: AsyncSession,
    branch_id: uuid.UUID,
    data: commands.EmployeeCreate,
    publisher: EventPublisher,
) -> models.Employee:
    await get_branch(session, branch_id)

    employee = models.Employee(
        branch_id=branch_id,
        full_name=data.full_name,
        role=data.role,
        keycloak_subject=data.keycloak_subject or None,
    )
    employee.assign_shifts((s.starts_at, s.ends_at) for s in data.shifts)
    session.add(employee)
    await session.commit()

    employee = await get_employee(session, employee.id)
    await publisher.publish(
        "employee.hired",
        employee_hired=events_pb2.EmployeeHired(
            employee_id=str(employee.id),
            branch_id=str(employee.branch_id),
            role=employee.role.value,
        ),
    )
    return employee


async def get_employee(session: AsyncSession, employee_id: uuid.UUID) -> models.Employee:
    employee = await session.scalar(
        select(models.Employee)
        .where(models.Employee.id == employee_id)
        .options(selectinload(models.Employee.shifts))
    )
    if employee is None:
        raise NotFoundError("employee", employee_id)
    return employee


async def list_employees(
    session: AsyncSession,
    branch_id: uuid.UUID,
    role: models.EmployeeRole | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[list[models.Employee], str]:
    await get_branch(session, branch_id)

    query = select(models.Employee).where(models.Employee.branch_id == branch_id)
    if role is not None:
        query = query.where(models.Employee.role == role)
    if cursor:
        last_name, last_id = decode_cursor(cursor)
        query = query.where(
            tuple_(models.Employee.full_name, models.Employee.id) > (last_name, last_id)
        )

    query = query.order_by(models.Employee.full_name, models.Employee.id).limit(limit + 1)
    rows = list(await session.scalars(query))

    has_more = len(rows) > limit
    rows = rows[:limit]
    return rows, encode_cursor(rows[-1].full_name, rows[-1].id) if has_more else ""


async def resolve_by_subject(session: AsyncSession, subject: str) -> models.Employee:
    """Какому сотруднику соответствует учётная запись.

    Спрашивает шлюз, чтобы передать ответ дальше в заголовке: иначе каждый
    сервис, проверяющий принадлежность, ходил бы сюда сам.
    """
    employee = await session.scalar(
        select(models.Employee).where(models.Employee.keycloak_subject == subject)
    )
    if employee is None:
        raise NotFoundError("учётная запись", subject)
    return employee


def _aware(value: datetime) -> datetime:
    """Дата без часового пояса считается UTC.

    В запросе можно передать просто дату — тогда FastAPI отдаёт наивное
    значение, а в базе время хранится со смещением. Сравнение таких значений
    в Python — TypeError и пятисотка на ровном месте.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def get_schedule(
    session: AsyncSession, employee_id: uuid.UUID, start_at: datetime, end_at: datetime
) -> tuple[models.Employee, list[models.WorkShift]]:
    start_at, end_at = _aware(start_at), _aware(end_at)
    employee = await get_employee(session, employee_id)

    # Пересечение с запрошенным окном, а не попадание целиком: смена может
    # начаться до его начала и закончиться после.
    shifts = [s for s in employee.shifts if s.starts_at < end_at and s.ends_at > start_at]
    shifts.sort(key=lambda s: s.starts_at)
    return employee, shifts
