from dataclasses import dataclass
from datetime import date as date_type, time

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database.models import Appointment, Doctor, DoctorAvailability, Patient
from .availability_service import slots_for_date

ACTIVE_APPOINTMENT_STATUSES = (
	"booked",
	"pending_doctor_confirmation",
	"confirmed",
	"alternative_proposed",
)

SPECIALIZATION_ALIASES = {
	"dermatology": ("dermatology", "dermatologist"),
	"cardiology": ("cardiology", "cardiologist"),
	"orthopedics": ("orthopedics", "orthopedic"),
	"pediatrics": ("pediatrics", "pediatrician"),
	"neurology": ("neurology", "neurologist"),
	"gynecology": ("gynecology", "gynecologist"),
	"dentistry": ("dentistry", "dentist"),
	"ophthalmology": ("ophthalmology", "ophthalmologist"),
}


@dataclass(frozen=True)
class AvailableSlot:
	doctor_id: int
	doctor: Doctor
	date: date_type
	start_time: time
	end_time: time



def specialization_terms(specialization: str) -> tuple[str, ...]:
	value = specialization.lower().strip()
	for canonical, aliases in SPECIALIZATION_ALIASES.items():
		if value == canonical or value in aliases:
			return aliases
	return (value,)


def search_availability(
	db: Session, appointment_date: date_type, doctor_id: int | None = None
) -> list[AvailableSlot]:
	query = db.query(Doctor)
	if doctor_id is not None:
		query = query.filter(Doctor.id == doctor_id)
	doctors = query.order_by(Doctor.name).all()
	return [
		AvailableSlot(
			doctor_id=doctor.id,
			doctor=doctor,
			date=appointment_date,
			start_time=time.fromisoformat(slot["start_time"]),
			end_time=time.fromisoformat(slot["end_time"]),
		)
		for doctor in doctors
		for slot in slots_for_date(db, doctor, appointment_date)
	]


def search_availability_by_specialization(
	db: Session,
	appointment_date: date_type,
	specialization: str,
	appointment_time: time | None = None,
) -> list[tuple[AvailableSlot, Doctor]]:
	terms = specialization_terms(specialization)
	doctors = (
		db.query(Doctor)
		.filter(
			or_(*(Doctor.specialization.ilike(f"%{term}%") for term in terms))
		)
		.order_by(Doctor.name)
		.all()
	)
	return [
		(
			AvailableSlot(
				doctor_id=doctor.id,
				doctor=doctor,
				date=appointment_date,
				start_time=time.fromisoformat(slot["start_time"]),
				end_time=time.fromisoformat(slot["end_time"]),
			),
			doctor,
		)
		for doctor in doctors
		for slot in slots_for_date(db, doctor, appointment_date)
		if appointment_time is None
		or time.fromisoformat(slot["start_time"]) == appointment_time
	]


def find_available_doctors(
	db: Session,
	specialization: str,
	date: date_type | str,
	preferred_time: time | str,
) -> dict:
	"""Find doctors with an open slot matching the requested appointment."""
	try:
		appointment_date = (
			date_type.fromisoformat(date) if isinstance(date, str) else date
		)
		appointment_time = (
			time.fromisoformat(preferred_time)
			if isinstance(preferred_time, str)
			else preferred_time
		)
	except ValueError as error:
		raise ValueError("Invalid appointment date or time") from error

	rows = search_availability_by_specialization(
		db, appointment_date, specialization, appointment_time
	)
	return {
		"available": bool(rows),
		"doctors": [
			{
				"id": doctor.id,
				"name": doctor.name,
				"specialization": doctor.specialization,
				"time": slot.start_time.strftime("%H:%M"),
			}
			for slot, doctor in rows
		],
	}


def book_appointment(
	db: Session,
	patient_id: int,
	doctor_id: int,
	appointment_date: date_type,
	appointment_time: time,
	symptoms: str | None,
	status: str = "pending_doctor_confirmation",
) -> Appointment:
	if db.get(Patient, patient_id) is None:
		raise HTTPException(status_code=404, detail="Patient not found")
	if db.get(Doctor, doctor_id) is None:
		raise HTTPException(status_code=404, detail="Doctor not found")

	availability = db.query(DoctorAvailability).filter(
		DoctorAvailability.doctor_id == doctor_id,
		DoctorAvailability.date == appointment_date,
		DoctorAvailability.start_time <= appointment_time,
		DoctorAvailability.end_time > appointment_time,
		DoctorAvailability.is_available.is_(True),
	).first()
	if availability is None:
		raise HTTPException(status_code=409, detail="The requested time is unavailable")

	occupied = db.query(Appointment).filter(
		Appointment.doctor_id == doctor_id,
		Appointment.appointment_date == appointment_date,
		Appointment.appointment_time == appointment_time,
		Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
	).first()
	if occupied is not None:
		raise HTTPException(status_code=409, detail="The requested time is already booked")

	appointment = Appointment(
		patient_id=patient_id,
		doctor_id=doctor_id,
		appointment_date=appointment_date,
		appointment_time=appointment_time,
		status=status,
		symptoms=symptoms,
	)
	db.add(appointment)
	db.commit()
	db.refresh(appointment)
	return appointment
