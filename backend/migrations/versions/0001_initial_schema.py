"""Create the legacy patient, doctor, and appointment tables.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
	op.create_table(
		"patients",
		sa.Column("id", sa.Integer(), primary_key=True),
		sa.Column("name", sa.String(), nullable=False),
		sa.Column("phone", sa.String(), nullable=True),
		sa.Column("email", sa.String(), nullable=True),
		sa.Column("age", sa.Integer(), nullable=True),
		sa.Column("gender", sa.String(), nullable=True),
		sa.Column("created_at", sa.DateTime(), nullable=True),
	)
	op.create_index("ix_patients_id", "patients", ["id"])
	op.create_table(
		"patient_credentials",
		sa.Column(
			"patient_id",
			sa.Integer(),
			sa.ForeignKey("patients.id"),
			primary_key=True,
		),
		sa.Column("email", sa.String(), nullable=False, unique=True),
		sa.Column("password_hash", sa.String(), nullable=False),
		sa.Column("role", sa.String(), nullable=False),
	)
	op.create_index(
		"ix_patient_credentials_email", "patient_credentials", ["email"], unique=True
	)
	op.create_table(
		"doctors",
		sa.Column("id", sa.Integer(), primary_key=True),
		sa.Column("name", sa.String(), nullable=False),
		sa.Column("email", sa.String(), nullable=True),
		sa.Column("specialization", sa.String(), nullable=True),
		sa.Column("hospital", sa.String(), nullable=True),
		sa.Column("experience", sa.Integer(), nullable=True),
		sa.Column("consultation_fee", sa.Float(), nullable=True),
		sa.Column("available_days", sa.String(), nullable=True),
	)
	op.create_index("ix_doctors_id", "doctors", ["id"])
	op.create_table(
		"doctor_availability",
		sa.Column("id", sa.Integer(), primary_key=True),
		sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id"), nullable=False),
		sa.Column("date", sa.Date(), nullable=False),
		sa.Column("start_time", sa.Time(), nullable=False),
		sa.Column("end_time", sa.Time(), nullable=False),
		sa.Column("is_available", sa.Boolean(), nullable=True),
	)
	op.create_index("ix_doctor_availability_id", "doctor_availability", ["id"])
	op.create_table(
		"appointments",
		sa.Column("id", sa.Integer(), primary_key=True),
		sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
		sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id"), nullable=False),
		sa.Column("appointment_date", sa.Date(), nullable=False),
		sa.Column("appointment_time", sa.Time(), nullable=False),
		sa.Column("status", sa.String(), nullable=True),
		sa.Column("symptoms", sa.String(), nullable=True),
		sa.Column("created_at", sa.DateTime(), nullable=True),
	)
	op.create_index("ix_appointments_id", "appointments", ["id"])


def downgrade() -> None:
	op.drop_index("ix_appointments_id", table_name="appointments")
	op.drop_table("appointments")
	op.drop_index("ix_doctor_availability_id", table_name="doctor_availability")
	op.drop_table("doctor_availability")
	op.drop_index("ix_doctors_id", table_name="doctors")
	op.drop_table("doctors")
	op.drop_index("ix_patient_credentials_email", table_name="patient_credentials")
	op.drop_table("patient_credentials")
	op.drop_index("ix_patients_id", table_name="patients")
	op.drop_table("patients")
