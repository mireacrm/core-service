"""Переименование роли master в specialist

Revision ID: 0003_role_specialist
Revises: 0002_shift_no_overlap
Create Date: 2026-09-09
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003_role_specialist"
down_revision: Union[str, None] = "0002_shift_no_overlap"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # RENAME VALUE сохраняет данные: строки со старым значением просто
    # начинают читаться под новым именем.
    op.execute("ALTER TYPE employee_role RENAME VALUE 'MASTER' TO 'SPECIALIST'")


def downgrade() -> None:
    op.execute("ALTER TYPE employee_role RENAME VALUE 'SPECIALIST' TO 'MASTER'")
