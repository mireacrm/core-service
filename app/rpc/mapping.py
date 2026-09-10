"""Перевод доменных моделей в сообщения protobuf."""

from mirea.core.v1 import core_pb2

from app import models

ROLE_TO_PROTO = {
    models.EmployeeRole.ADMIN: core_pb2.EMPLOYEE_ROLE_ADMIN,
    models.EmployeeRole.MANAGER: core_pb2.EMPLOYEE_ROLE_MANAGER,
    models.EmployeeRole.SPECIALIST: core_pb2.EMPLOYEE_ROLE_SPECIALIST,
}
ROLE_FROM_PROTO = {value: key for key, value in ROLE_TO_PROTO.items()}


def branch(value: models.Branch) -> core_pb2.Branch:
    return core_pb2.Branch(
        id=str(value.id),
        company_id=str(value.company_id),
        name=value.name,
        address=value.address,
        timezone=value.timezone,
    )


def employee(value: models.Employee) -> core_pb2.Employee:
    return core_pb2.Employee(
        id=str(value.id),
        branch_id=str(value.branch_id),
        full_name=value.full_name,
        role=ROLE_TO_PROTO[value.role],
        is_active=value.is_active,
    )
