"""Домен против настоящего Postgres: транзакции, ограничения, публикация событий."""

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from mireacrm_common import tracing
from mireacrm_common.db import create_engine, create_session_factory
from mireacrm_common.errors import ConflictError, NotFoundError
from mireacrm_common.health import check_readiness
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import commands, domain
from app.models import EmployeeRole

DAY = datetime(2026, 9, 10, tzinfo=UTC)
_UNREACHABLE_DSN = "postgresql+asyncpg://core_user:core_pass@127.0.0.1:1/nope"


def at(hour: int) -> datetime:
    return DAY + timedelta(hours=hour)


async def make_branch(session, publisher) -> uuid.UUID:
    company = await domain.create_company(
        session, commands.CompanyCreate(name="Локон", inn="7701234567")
    )
    branch = await domain.open_branch(
        session,
        company.id,
        commands.BranchCreate(name="На Тверской", address="Тверская 15"),
        publisher,
    )
    return branch.id


class TestCompany:
    async def test_created(self, session, publisher):
        company = await domain.create_company(
            session, commands.CompanyCreate(name="Локон", inn="7701234567")
        )

        assert company.id is not None
        assert company.created_at is not None

    async def test_duplicate_inn_rejected(self, session, publisher):
        await domain.create_company(session, commands.CompanyCreate(name="Локон", inn="7701234567"))

        with pytest.raises(ConflictError, match="ИНН"):
            await domain.create_company(
                session, commands.CompanyCreate(name="Другая", inn="7701234567")
            )


class TestBranch:
    async def test_opened_publishes_event(self, session, publisher):
        branch_id = await make_branch(session, publisher)

        assert publisher.routing_keys() == ["branch.opened"]
        _, payload = publisher.published[0]
        assert payload.branch_id == str(branch_id)
        assert payload.name == "На Тверской"

    async def test_event_carries_current_traceparent(self, session, publisher):
        header = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        tracing.set_current(header)

        await make_branch(session, publisher)

        assert publisher.published[0][1] is not None
        assert publisher.envelopes[0] == header

    async def test_unknown_company_rejected(self, session, publisher):
        with pytest.raises(NotFoundError):
            await domain.open_branch(
                session,
                uuid.uuid4(),
                commands.BranchCreate(name="X", address="Y"),
                publisher,
            )
        assert publisher.published == []


class TestEmployee:
    async def test_hired_with_shifts(self, session, publisher):
        branch_id = await make_branch(session, publisher)

        employee = await domain.hire_employee(
            session,
            branch_id,
            commands.EmployeeCreate(
                full_name="Анна Специалистова",
                role=EmployeeRole.SPECIALIST,
                shifts=[commands.ShiftIn(starts_at=at(9), ends_at=at(18))],
            ),
            publisher,
        )

        assert len(employee.shifts) == 1
        assert publisher.routing_keys() == ["branch.opened", "employee.hired"]

    async def test_overlapping_shifts_rejected_before_insert(self, session, publisher):
        branch_id = await make_branch(session, publisher)

        with pytest.raises(ConflictError):
            await domain.hire_employee(
                session,
                branch_id,
                commands.EmployeeCreate(
                    full_name="Пересекающийся",
                    role=EmployeeRole.SPECIALIST,
                    shifts=[
                        commands.ShiftIn(starts_at=at(9), ends_at=at(18)),
                        commands.ShiftIn(starts_at=at(14), ends_at=at(20)),
                    ],
                ),
                publisher,
            )

        assert "employee.hired" not in publisher.routing_keys()

    async def test_database_rejects_overlap_bypassing_aggregate(self, session, publisher):
        """Ограничение EXCLUDE ловит запись мимо доменной логики."""
        branch_id = await make_branch(session, publisher)
        employee = await domain.hire_employee(
            session,
            branch_id,
            commands.EmployeeCreate(
                full_name="Анна",
                role=EmployeeRole.SPECIALIST,
                shifts=[commands.ShiftIn(starts_at=at(9), ends_at=at(18))],
            ),
            publisher,
        )

        with pytest.raises(IntegrityError, match="work_shifts_no_overlap"):
            await session.execute(
                text(
                    "INSERT INTO work_shifts (id, employee_id, starts_at, ends_at) "
                    "VALUES (gen_random_uuid(), :eid, :s, :e)"
                ),
                {"eid": employee.id, "s": at(10), "e": at(12)},
            )
        await session.rollback()

    async def test_unknown_branch_rejected(self, session, publisher):
        with pytest.raises(NotFoundError):
            await domain.hire_employee(
                session,
                uuid.uuid4(),
                commands.EmployeeCreate(full_name="X", role=EmployeeRole.SPECIALIST),
                publisher,
            )


class TestListing:
    async def test_paginates_by_cursor(self, session, publisher):
        branch_id = await make_branch(session, publisher)
        for name in ("Борис", "Анна", "Виктор"):
            await domain.hire_employee(
                session,
                branch_id,
                commands.EmployeeCreate(full_name=name, role=EmployeeRole.SPECIALIST),
                publisher,
            )

        first, cursor = await domain.list_employees(session, branch_id, limit=2)
        assert [e.full_name for e in first] == ["Анна", "Борис"]
        assert cursor

        second, next_cursor = await domain.list_employees(
            session, branch_id, limit=2, cursor=cursor
        )
        assert [e.full_name for e in second] == ["Виктор"]
        assert next_cursor == ""

    async def test_filters_by_role(self, session, publisher):
        branch_id = await make_branch(session, publisher)
        await domain.hire_employee(
            session,
            branch_id,
            commands.EmployeeCreate(full_name="Специалист", role=EmployeeRole.SPECIALIST),
            publisher,
        )
        await domain.hire_employee(
            session,
            branch_id,
            commands.EmployeeCreate(full_name="Админ", role=EmployeeRole.MANAGER),
            publisher,
        )

        masters, _ = await domain.list_employees(session, branch_id, role=EmployeeRole.SPECIALIST)
        assert [e.full_name for e in masters] == ["Специалист"]


class TestSchedule:
    async def test_returns_only_intersecting_shifts(self, session, publisher):
        branch_id = await make_branch(session, publisher)
        employee = await domain.hire_employee(
            session,
            branch_id,
            commands.EmployeeCreate(
                full_name="Анна",
                role=EmployeeRole.SPECIALIST,
                shifts=[
                    commands.ShiftIn(starts_at=at(9), ends_at=at(18)),
                    commands.ShiftIn(starts_at=at(48), ends_at=at(56)),
                ],
            ),
            publisher,
        )

        _, shifts = await domain.get_schedule(session, employee.id, at(0), at(24))
        assert len(shifts) == 1

    async def test_shift_partially_covering_window_included(self, session, publisher):
        """Смена началась до окна и закончилась внутри — должна попасть."""
        branch_id = await make_branch(session, publisher)
        employee = await domain.hire_employee(
            session,
            branch_id,
            commands.EmployeeCreate(
                full_name="Анна",
                role=EmployeeRole.SPECIALIST,
                shifts=[commands.ShiftIn(starts_at=at(6), ends_at=at(14))],
            ),
            publisher,
        )

        _, shifts = await domain.get_schedule(session, employee.id, at(12), at(20))
        assert len(shifts) == 1


class TestReadiness:
    async def test_reports_ok_when_database_reachable(self, context):
        report = await check_readiness(context)

        assert report.checks["database"] == "ok"

    async def test_reports_error_when_database_unreachable(self, context):
        broken = replace(
            context, sessions=create_session_factory(create_engine(_UNREACHABLE_DSN))
        )

        report = await check_readiness(broken)

        assert not report.ready
        assert report.checks["database"].startswith("error:")
