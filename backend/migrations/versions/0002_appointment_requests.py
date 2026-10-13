"""Add doctor-approved appointment requests and notification outbox.

Revision ID: 0002_requests
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_requests"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
	bind = op.get_bind()
	inspector = inspect(bind)
	doctor_columns = {column["name"] for column in inspector.get_columns("doctors")}
	for name in ("email", "available_days"):
		if name not in doctor_columns:
			op.add_column("doctors", sa.Column(name, sa.String(), nullable=True))

	op.create_table(
		"doctor_credentials",
		sa.Column(
			"doctor_id",
			sa.Integer(),
			sa.ForeignKey("doctors.id"),
			primary_key=True,
		),
		sa.Column("email", sa.String(), nullable=False),
		sa.Column("password_hash", sa.String(), nullable=False),
	)
	op.create_index(
		"ix_doctor_credentials_email", "doctor_credentials", ["email"], unique=True
	)

	op.create_index(
		"uq_confirmed_appointment_slot",
		"appointments",
		["doctor_id", "appointment_date", "appointment_time"],
		unique=True,
		postgresql_where=sa.text("status = 'confirmed'"),
		sqlite_where=sa.text("status = 'confirmed'"),
	)
	op.create_table(
		"appointment_requests",
		sa.Column("id", sa.Integer(), primary_key=True),
		sa.Column(
			"patient_id",
			sa.Integer(),
			sa.ForeignKey("patients.id"),
			nullable=False,
		),
		sa.Column(
			"doctor_id",
			sa.Integer(),
			sa.ForeignKey("doctors.id"),
			nullable=False,
		),
		sa.Column(
			"appointment_id",
			sa.Integer(),
			sa.ForeignKey("appointments.id"),
			nullable=True,
		),
		sa.Column("idempotency_key", sa.String(length=64), nullable=True),
		sa.Column("requested_date", sa.Date(), nullable=False),
		sa.Column("requested_time", sa.Time(), nullable=False),
		sa.Column("reason", sa.String(length=2000), nullable=True),
		sa.Column(
			"status",
			sa.String(length=24),
			server_default="PENDING",
			nullable=False,
		),
		sa.Column("proposed_date", sa.Date(), nullable=True),
		sa.Column("proposed_time", sa.Time(), nullable=True),
		sa.Column("rejection_reason", sa.String(length=1000), nullable=True),
		sa.Column("decision_details", sa.Text(), nullable=True),
		sa.Column("decided_at", sa.DateTime(), nullable=True),
		sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
		sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
		sa.CheckConstraint(
			"status IN ('PENDING', 'APPROVED', 'REJECTED', 'COUNTER_PROPOSED', 'CONFIRMED')",
			name="ck_appointment_request_status",
		),
		sa.UniqueConstraint(
			"patient_id", "idempotency_key", name="uq_appointment_request_idempotency"
		),
	)
	op.create_index("ix_appointment_requests_id", "appointment_requests", ["id"])
	op.create_index(
		"ix_appointment_requests_patient_id", "appointment_requests", ["patient_id"]
	)
	op.create_index(
		"ix_appointment_requests_doctor_id", "appointment_requests", ["doctor_id"]
	)
	op.create_index(
		"ix_appointment_requests_status", "appointment_requests", ["status"]
	)
	op.create_index(
		"uq_active_patient_appointment_request",
		"appointment_requests",
		["patient_id", "doctor_id", "requested_date", "requested_time"],
		unique=True,
		postgresql_where=sa.text(
			"status IN ('PENDING', 'APPROVED', 'COUNTER_PROPOSED', 'CONFIRMED')"
		),
		sqlite_where=sa.text(
			"status IN ('PENDING', 'APPROVED', 'COUNTER_PROPOSED', 'CONFIRMED')"
		),
	)
	op.create_table(
		"appointment_notifications",
		sa.Column("id", sa.Integer(), primary_key=True),
		sa.Column(
			"request_id",
			sa.Integer(),
			sa.ForeignKey("appointment_requests.id"),
			nullable=False,
		),
		sa.Column("notification_type", sa.String(length=40), nullable=False),
		sa.Column("recipient", sa.String(length=320), nullable=False),
		sa.Column("status", sa.String(length=16), server_default="PENDING", nullable=False),
		sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
		sa.Column("last_error", sa.String(length=80), nullable=True),
		sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
		sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
		sa.Column("sent_at", sa.DateTime(), nullable=True),
		sa.CheckConstraint(
			"status IN ('PENDING', 'SENDING', 'SENT', 'FAILED')",
			name="ck_appointment_notification_status",
		),
		sa.UniqueConstraint(
			"request_id",
			"notification_type",
			name="uq_appointment_notification_event",
		),
	)
	op.create_index(
		"ix_appointment_notifications_id", "appointment_notifications", ["id"]
	)
	op.create_index(
		"ix_appointment_notifications_request_id",
		"appointment_notifications",
		["request_id"],
	)
	op.create_index(
		"ix_appointment_notifications_status",
		"appointment_notifications",
		["status"],
	)


def downgrade() -> None:
	op.drop_index("ix_appointment_notifications_status", table_name="appointment_notifications")
	op.drop_index(
		"ix_appointment_notifications_request_id",
		table_name="appointment_notifications",
	)
	op.drop_index("ix_appointment_notifications_id", table_name="appointment_notifications")
	op.drop_table("appointment_notifications")
	op.drop_index(
		"uq_active_patient_appointment_request", table_name="appointment_requests"
	)
	op.drop_index("ix_appointment_requests_status", table_name="appointment_requests")
	op.drop_index("ix_appointment_requests_doctor_id", table_name="appointment_requests")
	op.drop_index("ix_appointment_requests_patient_id", table_name="appointment_requests")
	op.drop_index("ix_appointment_requests_id", table_name="appointment_requests")
	op.drop_table("appointment_requests")
	op.drop_index(
		"uq_confirmed_appointment_slot", table_name="appointments"
	)
	op.drop_index("ix_doctor_credentials_email", table_name="doctor_credentials")
	op.drop_table("doctor_credentials")
