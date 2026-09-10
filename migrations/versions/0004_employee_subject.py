"""Связь сотрудника с учётной записью

Revision ID: 0004_employee_subject
Revises: 0003_role_specialist
Create Date: 2026-09-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_employee_subject"
down_revision: Union[str, None] = "0003_role_specialist"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Заполнено не у всех: сотрудник может работать без учётной записи,
    # а учётная запись — не соответствовать ни одному сотруднику.
    op.add_column("employees", sa.Column("keycloak_subject", sa.String(64), nullable=True))
    # Уникальность частичная: NULL допускается сколько угодно раз, но одна
    # учётная запись не может оказаться двумя сотрудниками сразу.
    op.create_index(
        "uq_employees_keycloak_subject",
        "employees",
        ["keycloak_subject"],
        unique=True,
        postgresql_where=sa.text("keycloak_subject IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_employees_keycloak_subject", table_name="employees")
    op.drop_column("employees", "keycloak_subject")
