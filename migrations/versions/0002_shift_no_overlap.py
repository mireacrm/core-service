"""Запрет пересекающихся смен у одного сотрудника

Revision ID: 0002_shift_no_overlap
Revises: 2ede45a8d02e
Create Date: 2026-09-09
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_shift_no_overlap"
down_revision: Union[str, None] = "2ede45a8d02e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE work_shifts
        ADD CONSTRAINT work_shifts_no_overlap
        EXCLUDE USING gist (
            employee_id WITH =,
            tstzrange(starts_at, ends_at) WITH &&
        )
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE work_shifts DROP CONSTRAINT work_shifts_no_overlap")
