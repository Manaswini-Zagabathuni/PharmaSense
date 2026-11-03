"""Establish the Phase 0 schema baseline.

Revision ID: 20261021_0001
Revises:
Create Date: 2026-10-21
"""

from collections.abc import Sequence

revision: str = "20261021_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Establish the Alembic version; domain tables begin in later phases."""


def downgrade() -> None:
    """Remove no domain objects; Alembic manages its own version table."""
