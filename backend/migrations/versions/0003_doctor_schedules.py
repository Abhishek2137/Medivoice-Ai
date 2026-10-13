"""Add doctor profiles and recurring weekly availability.

Revision ID: 0003_doctor_schedules
Revises: 0002_requests
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_doctor_schedules"
down_revision = "0002_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
	columns = {
		column["name"]
		for column in inspect(op.get_bind()).get_columns("doctors")
	}
	if "profile_image_url" not in columns:
		op.add_column(
			"doctors", sa.Column("profile_image_url", sa.String(length=1000), nullable=True)
		)
	if "consultation_info" not in columns:
		op.add_column("doctors", sa.Column("consultation_info", sa.Text(), nullable=True))
	if "appointment_duration_minutes" not in columns:
		op.add_column(
			"doctors",
			sa.Column(
				"appointment_duration_minutes",
				sa.Integer(),
				nullable=False,
				server_default="30",
			),
		)

	op.create_table(
		"doctor_weekly_availability",
		sa.Column("id", sa.Integer(), primary_key=True),
		sa.Column(
			"doctor_id", sa.Integer(), sa.ForeignKey("doctors.id"), nullable=False
		),
		sa.Column("weekday", sa.Integer(), nullable=False),
		sa.Column("start_time", sa.Time(), nullable=False),
		sa.Column("end_time", sa.Time(), nullable=False),
		sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_doctor_weekday"),
		sa.CheckConstraint(
			"start_time < end_time", name="ck_doctor_weekly_time_range"
		),
	)
	op.create_index(
		"ix_doctor_weekly_availability_id",
		"doctor_weekly_availability",
		["id"],
	)
	op.create_index(
		"ix_doctor_weekly_availability_doctor_id",
		"doctor_weekly_availability",
		["doctor_id"],
	)
	op.create_index(
		"ix_doctor_weekly_day",
		"doctor_weekly_availability",
		["doctor_id", "weekday"],
	)


def downgrade() -> None:
	op.drop_index("ix_doctor_weekly_day", table_name="doctor_weekly_availability")
	op.drop_index(
		"ix_doctor_weekly_availability_doctor_id",
		table_name="doctor_weekly_availability",
	)
	op.drop_index(
		"ix_doctor_weekly_availability_id",
		table_name="doctor_weekly_availability",
	)
	op.drop_table("doctor_weekly_availability")
	op.drop_column("doctors", "appointment_duration_minutes")
	op.drop_column("doctors", "consultation_info")
	op.drop_column("doctors", "profile_image_url")
