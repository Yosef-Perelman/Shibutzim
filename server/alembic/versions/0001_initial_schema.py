"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-10 13:53:25.903462

"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Extensions are created in a migration, not by hand (database-rules).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "handbook_chunks",
        sa.Column("section_title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(768), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_handbook_chunks")),
    )
    op.create_table(
        "schedules",
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "published",
                name="schedule_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedules")),
        sa.UniqueConstraint("week_start", name=op.f("uq_schedules_week_start")),
    )
    op.create_table(
        "shift_templates",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("required_staff", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.CheckConstraint(
            "required_staff > 0", name=op.f("ck_shift_templates_required_staff_positive")
        ),
        sa.CheckConstraint(
            "weekday BETWEEN 0 AND 6", name=op.f("ck_shift_templates_weekday_range")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shift_templates")),
    )
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "manager",
                "employee",
                name="role",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("hourly_rate", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "shifts",
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("required_staff", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_shifts_ends_after_starts")),
        sa.CheckConstraint("required_staff > 0", name=op.f("ck_shifts_required_staff_positive")),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["shift_templates.id"],
            name=op.f("fk_shifts_template_id_shift_templates"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shifts")),
        sa.UniqueConstraint(
            "template_id", "week_start", name=op.f("uq_shifts_template_id_week_start")
        ),
    )
    op.create_index(op.f("ix_shifts_template_id"), "shifts", ["template_id"], unique=False)
    op.create_index("ix_shifts_week_start", "shifts", ["week_start"], unique=False)
    op.create_table(
        "time_entries",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("clock_in", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clock_out", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "source",
            sa.Enum(
                "clock",
                "manual",
                name="time_entry_source",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.CheckConstraint(
            "clock_out IS NULL OR clock_out > clock_in",
            name=op.f("ck_time_entries_clock_out_after_clock_in"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_time_entries_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_time_entries_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_time_entries")),
    )
    op.create_index(
        op.f("ix_time_entries_created_by"), "time_entries", ["created_by"], unique=False
    )
    op.create_index(
        "ix_time_entries_user_id_clock_in", "time_entries", ["user_id", "clock_in"], unique=False
    )
    op.create_index(
        "uq_time_entries_one_open_per_user",
        "time_entries",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("clock_out IS NULL"),
    )
    op.create_table(
        "tool_call_logs",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tool", sa.String(length=100), nullable=False),
        sa.Column("args", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("result_size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_tool_call_logs_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_call_logs")),
    )
    op.create_index(op.f("ix_tool_call_logs_user_id"), "tool_call_logs", ["user_id"], unique=False)
    op.create_table(
        "assignments",
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["schedules.id"],
            name=op.f("fk_assignments_schedule_id_schedules"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shift_id"],
            ["shifts.id"],
            name=op.f("fk_assignments_shift_id_shifts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_assignments_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignments")),
        sa.UniqueConstraint(
            "schedule_id",
            "shift_id",
            "user_id",
            name=op.f("uq_assignments_schedule_id_shift_id_user_id"),
        ),
    )
    op.create_index(
        op.f("ix_assignments_schedule_id"), "assignments", ["schedule_id"], unique=False
    )
    op.create_index(op.f("ix_assignments_shift_id"), "assignments", ["shift_id"], unique=False)
    op.create_index(op.f("ix_assignments_user_id"), "assignments", ["user_id"], unique=False)
    op.create_table(
        "availabilities",
        sa.Column("shift_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "available",
                "preferred",
                "unavailable",
                name="availability_status",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.ForeignKeyConstraint(
            ["shift_id"],
            ["shifts.id"],
            name=op.f("fk_availabilities_shift_id_shifts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_availabilities_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_availabilities")),
        sa.UniqueConstraint("shift_id", "user_id", name=op.f("uq_availabilities_shift_id_user_id")),
    )
    op.create_index(
        op.f("ix_availabilities_shift_id"), "availabilities", ["shift_id"], unique=False
    )
    op.create_index(op.f("ix_availabilities_user_id"), "availabilities", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_availabilities_user_id"), table_name="availabilities")
    op.drop_index(op.f("ix_availabilities_shift_id"), table_name="availabilities")
    op.drop_table("availabilities")
    op.drop_index(op.f("ix_assignments_user_id"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_shift_id"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_schedule_id"), table_name="assignments")
    op.drop_table("assignments")
    op.drop_index(op.f("ix_tool_call_logs_user_id"), table_name="tool_call_logs")
    op.drop_table("tool_call_logs")
    op.drop_index(
        "uq_time_entries_one_open_per_user",
        table_name="time_entries",
        postgresql_where=sa.text("clock_out IS NULL"),
    )
    op.drop_index("ix_time_entries_user_id_clock_in", table_name="time_entries")
    op.drop_index(op.f("ix_time_entries_created_by"), table_name="time_entries")
    op.drop_table("time_entries")
    op.drop_index("ix_shifts_week_start", table_name="shifts")
    op.drop_index(op.f("ix_shifts_template_id"), table_name="shifts")
    op.drop_table("shifts")
    op.drop_table("users")
    op.drop_table("shift_templates")
    op.drop_table("schedules")
    op.drop_table("handbook_chunks")

    op.execute("DROP EXTENSION IF EXISTS vector")
