from datetime import datetime
from sqlalchemy import (
	Column,
	Integer,
	String,
	DateTime,
	Boolean,
	ForeignKey,
	Date,
	Time,
	Float,
	Text,
	Index,
	UniqueConstraint,
	CheckConstraint,
	text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Patient(Base):
	__tablename__ = "patients"

	id = Column(Integer, primary_key=True, index=True)
	name = Column(String, nullable=False)
	phone = Column(String, nullable=True)
	email = Column(String, nullable=True)
	age = Column(Integer, nullable=True)
	gender = Column(String, nullable=True)
	created_at = Column(DateTime, default=datetime.utcnow)
	credential = relationship(
		"PatientCredential", back_populates="patient", uselist=False
	)


class PatientCredential(Base):
	__tablename__ = "patient_credentials"

	patient_id = Column(Integer, ForeignKey("patients.id"), primary_key=True)
	email = Column(String, nullable=False, unique=True, index=True)
	password_hash = Column(String, nullable=False)
	role = Column(String, nullable=False, default="patient")

	patient = relationship("Patient", back_populates="credential")


class DoctorCredential(Base):
	__tablename__ = "doctor_credentials"

	doctor_id = Column(Integer, ForeignKey("doctors.id"), primary_key=True)
	email = Column(String, nullable=False, unique=True, index=True)
	password_hash = Column(String, nullable=False)
	doctor = relationship("Doctor", backref="credential")


class Doctor(Base):
	__tablename__ = "doctors"

	id = Column(Integer, primary_key=True, index=True)
	name = Column(String, nullable=False)
	email = Column(String, nullable=True)
	specialization = Column(String, nullable=True)
	hospital = Column(String, nullable=True)
	experience = Column(Integer, nullable=True)
	consultation_fee = Column(Float, nullable=True)
	available_days = Column(String, nullable=True)
	profile_image_url = Column(String(1000), nullable=True)
	consultation_info = Column(Text, nullable=True)
	appointment_duration_minutes = Column(Integer, nullable=False, default=30)


class DoctorAvailability(Base):
	__tablename__ = "doctor_availability"

	id = Column(Integer, primary_key=True, index=True)
	doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
	date = Column(Date, nullable=False)
	start_time = Column(Time, nullable=False)
	end_time = Column(Time, nullable=False)
	is_available = Column(Boolean, default=True)

	doctor = relationship("Doctor", backref="availability")


class DoctorWeeklyAvailability(Base):
	__tablename__ = "doctor_weekly_availability"

	id = Column(Integer, primary_key=True, index=True)
	doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False, index=True)
	weekday = Column(Integer, nullable=False)
	start_time = Column(Time, nullable=False)
	end_time = Column(Time, nullable=False)

	doctor = relationship("Doctor", backref="weekly_availability")

	__table_args__ = (
		CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_doctor_weekday"),
		CheckConstraint("start_time < end_time", name="ck_doctor_weekly_time_range"),
		Index("ix_doctor_weekly_day", "doctor_id", "weekday"),
	)


class Appointment(Base):
	__tablename__ = "appointments"

	id = Column(Integer, primary_key=True, index=True)
	patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
	doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
	appointment_date = Column(Date, nullable=False)
	appointment_time = Column(Time, nullable=False)
	status = Column(String, nullable=True)
	symptoms = Column(String, nullable=True)
	created_at = Column(DateTime, default=datetime.utcnow)

	patient = relationship("Patient", backref="appointments")
	doctor = relationship("Doctor", backref="appointments")

	__table_args__ = (
		Index(
			"uq_confirmed_appointment_slot",
			"doctor_id",
			"appointment_date",
			"appointment_time",
			unique=True,
			postgresql_where=text("status = 'confirmed'"),
			sqlite_where=text("status = 'confirmed'"),
		),
	)


class AppointmentRequest(Base):
	__tablename__ = "appointment_requests"

	id = Column(Integer, primary_key=True, index=True)
	patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
	doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False, index=True)
	appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
	idempotency_key = Column(String(64), nullable=True)
	requested_date = Column(Date, nullable=False)
	requested_time = Column(Time, nullable=False)
	reason = Column(String(2000), nullable=True)
	status = Column(String(24), nullable=False, default="PENDING", index=True)
	proposed_date = Column(Date, nullable=True)
	proposed_time = Column(Time, nullable=True)
	rejection_reason = Column(String(1000), nullable=True)
	decision_details = Column(Text, nullable=True)
	decided_at = Column(DateTime, nullable=True)
	created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
	updated_at = Column(
		DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
	)

	patient = relationship("Patient", backref="appointment_requests")
	doctor = relationship("Doctor", backref="appointment_requests")
	appointment = relationship("Appointment")

	__table_args__ = (
		CheckConstraint(
			"status IN ('PENDING', 'APPROVED', 'REJECTED', 'COUNTER_PROPOSED', 'CONFIRMED')",
			name="ck_appointment_request_status",
		),
		UniqueConstraint(
			"patient_id", "idempotency_key", name="uq_appointment_request_idempotency"
		),
		Index(
			"uq_active_patient_appointment_request",
			"patient_id",
			"doctor_id",
			"requested_date",
			"requested_time",
			unique=True,
			sqlite_where=text("status IN ('PENDING', 'APPROVED', 'COUNTER_PROPOSED', 'CONFIRMED')"),
			postgresql_where=text(
				"status IN ('PENDING', 'APPROVED', 'COUNTER_PROPOSED', 'CONFIRMED')"
			),
		),
	)


class AppointmentNotification(Base):
	__tablename__ = "appointment_notifications"

	id = Column(Integer, primary_key=True, index=True)
	request_id = Column(
		Integer, ForeignKey("appointment_requests.id"), nullable=False, index=True
	)
	notification_type = Column(String(40), nullable=False)
	recipient = Column(String(320), nullable=False)
	status = Column(String(16), nullable=False, default="PENDING", index=True)
	attempt_count = Column(Integer, nullable=False, default=0)
	last_error = Column(String(80), nullable=True)
	created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
	updated_at = Column(
		DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
	)
	sent_at = Column(DateTime, nullable=True)

	request = relationship("AppointmentRequest", backref="notifications")

	__table_args__ = (
		CheckConstraint(
			"status IN ('PENDING', 'SENDING', 'SENT', 'FAILED')",
			name="ck_appointment_notification_status",
		),
		UniqueConstraint(
			"request_id",
			"notification_type",
			name="uq_appointment_notification_event",
		),
	)
