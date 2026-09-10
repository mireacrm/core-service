"""Инвариант непересекающихся смен внутри агрегата Employee."""

from datetime import UTC, datetime, timedelta

import pytest
from mireacrm_common.errors import ConflictError

from app.models import Employee, EmployeeRole

DAY = datetime(2026, 9, 10, tzinfo=UTC)


def at(hour: int) -> datetime:
    return DAY + timedelta(hours=hour)


def make_employee() -> Employee:
    return Employee(full_name="Тест", role=EmployeeRole.SPECIALIST)


def test_shifts_are_sorted_regardless_of_input_order():
    employee = make_employee()
    employee.assign_shifts([(at(14), at(18)), (at(9), at(13))])

    assert [s.starts_at for s in employee.shifts] == [at(9), at(14)]


def test_overlapping_shifts_rejected():
    employee = make_employee()

    with pytest.raises(ConflictError, match="пересекаются"):
        employee.assign_shifts([(at(9), at(18)), (at(14), at(20))])


def test_shift_fully_inside_another_rejected():
    employee = make_employee()

    with pytest.raises(ConflictError):
        employee.assign_shifts([(at(9), at(20)), (at(12), at(14))])


def test_touching_shifts_allowed():
    """14:00-14:00 — не пересечение: интервал полуоткрытый."""
    employee = make_employee()
    employee.assign_shifts([(at(9), at(14)), (at(14), at(20))])

    assert len(employee.shifts) == 2


def test_empty_schedule_allowed():
    employee = make_employee()
    employee.assign_shifts([])

    assert employee.shifts == []


def test_assign_replaces_previous_schedule():
    employee = make_employee()
    employee.assign_shifts([(at(9), at(13))])
    employee.assign_shifts([(at(15), at(19))])

    assert [s.starts_at for s in employee.shifts] == [at(15)]
