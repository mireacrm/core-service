"""Принадлежность объекта: специалист работает только со своим.

Проверка стоит на границе HTTP, поэтому доменными вызовами она не видна —
тесты идут через настоящие маршруты и настоящую базу.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from mireacrm_common import identity

from app import commands, domain
from app.models import EmployeeRole

DAY = datetime(2026, 9, 10, tzinfo=UTC)
SUBJECT = "8f1c0e4e-0000-4000-8000-000000000001"
WINDOW = {"from": DAY.isoformat(), "to": (DAY + timedelta(days=1)).isoformat()}


def headers(role: str, employee_id: uuid.UUID | str = "") -> dict[str, str]:
    return {
        identity.HEADER_SUBJECT: SUBJECT,
        identity.HEADER_ROLES: role,
        identity.HEADER_EMPLOYEE: str(employee_id),
    }


@pytest.fixture
async def employees(session, publisher) -> tuple[uuid.UUID, uuid.UUID]:
    """Два специалиста в одном филиале: свой и чужой."""
    company = await domain.create_company(
        session, commands.CompanyCreate(name="Локон", inn="7701234567")
    )
    branch = await domain.open_branch(
        session, company.id,
        commands.BranchCreate(name="На Тверской", address="Тверская 15"), publisher,
    )
    shift = commands.ShiftIn(starts_at=DAY, ends_at=DAY + timedelta(hours=8))

    own = await domain.hire_employee(
        session, branch.id,
        commands.EmployeeCreate(
            full_name="Анна", role=EmployeeRole.SPECIALIST,
            shifts=[shift], keycloak_subject=SUBJECT,
        ),
        publisher,
    )
    other = await domain.hire_employee(
        session, branch.id,
        commands.EmployeeCreate(full_name="Борис", role=EmployeeRole.SPECIALIST, shifts=[shift]),
        publisher,
    )
    return own.id, other.id


class TestSchedule:
    async def test_specialist_sees_own(self, api, employees) -> None:
        own, _ = employees
        response = await api.get(
            f"/employees/{own}/schedule", params=WINDOW, headers=headers("specialist", own)
        )
        assert response.status_code == 200

    async def test_specialist_denied_foreign(self, api, employees) -> None:
        own, other = employees
        response = await api.get(
            f"/employees/{other}/schedule", params=WINDOW, headers=headers("specialist", own)
        )
        assert response.status_code == 403

    @pytest.mark.parametrize("role", ["admin", "manager"])
    async def test_privileged_sees_any(self, api, employees, role) -> None:
        _, other = employees
        response = await api.get(
            f"/employees/{other}/schedule", params=WINDOW, headers=headers(role)
        )
        assert response.status_code == 200

    async def test_account_without_employee_denied(self, api, employees) -> None:
        """Учётная запись без сотрудника не должна видеть ничего чужого."""
        _, other = employees
        response = await api.get(
            f"/employees/{other}/schedule", params=WINDOW, headers=headers("specialist")
        )
        assert response.status_code == 403

    async def test_forged_employee_header_is_all_it_takes(self, api, employees) -> None:
        """Заголовку доверяем: подделать его снаружи нельзя, шлюз его затирает.

        Тест фиксирует это как осознанное свойство модели доверия, а не
        случайность: вся защита периметра держится на затирании заголовков.
        """
        own, other = employees
        response = await api.get(
            f"/employees/{other}/schedule", params=WINDOW, headers=headers("specialist", other)
        )
        assert response.status_code == 200
        assert own != other


class TestNaiveWindow:
    async def test_bare_dates_accepted(self, api, employees) -> None:
        """В запросе можно передать просто дату, без часового пояса.

        Значения из базы приходят со смещением, и сравнение с наивной датой
        в Python — TypeError, то есть пятисотка вместо расписания.
        """
        own, _ = employees
        response = await api.get(
            f"/employees/{own}/schedule",
            params={"from": "2026-09-10", "to": "2026-09-11"},
            headers=headers("manager"),
        )
        assert response.status_code == 200
        assert len(response.json()["shifts"]) == 1


class TestResolution:
    async def test_finds_employee_by_subject(self, api, employees) -> None:
        own, _ = employees
        response = await api.get(f"/internal/employees/by-subject/{SUBJECT}")
        assert response.status_code == 200
        assert response.json()["employee_id"] == str(own)

    async def test_unknown_subject_is_404(self, api, employees) -> None:
        response = await api.get("/internal/employees/by-subject/никого-нет")
        assert response.status_code == 404

    async def test_employee_without_account_is_not_resolvable(
        self, api, employees, session
    ) -> None:
        _, other = employees
        found = await domain.resolve_by_subject(session, SUBJECT)
        assert found.id != other
