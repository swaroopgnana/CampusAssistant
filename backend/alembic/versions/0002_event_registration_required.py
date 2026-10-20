"""Add event registration requirement flag.

Revision ID: 0002_event_registration_required
Revises: 0001_initial
"""
import sqlalchemy as sa
from alembic import op


revision = "0002_event_registration_required"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("events")}
    if "registration_required" not in columns:
        op.add_column(
            "events",
            sa.Column("registration_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("events")}
    if "registration_required" in columns:
        op.drop_column("events", "registration_required")
