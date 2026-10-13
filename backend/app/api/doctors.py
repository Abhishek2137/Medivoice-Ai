from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..database.models import Doctor, DoctorAvailability, DoctorWeeklyAvailability
from ..services.appointment_service import specialization_terms
from ..services.availability_service import available_dates, slots_for_date
from ..services.auth_service import get_current_doctor

router = APIRouter(prefix="/doctors", tags=["doctors"])
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class WeeklyWindow(BaseModel):
	weekday: int = Field(ge=0, le=6)
	start_time: time
	end_time: time

	@model_validator(mode="after")
	def valid_range(self):
		if self.start_time.tzinfo or self.end_time.tzinfo or self.start_time >= self.end_time:
			raise ValueError("A working-hours range must end after it starts")
		return self


class WeeklyScheduleUpdate(BaseModel):
	appointment_duration_minutes: int = Field(default=30, ge=5, le=240)
	windows: list[WeeklyWindow] = Field(max_length=50)

	@model_validator(mode="after")
	def no_overlapping_windows(self):
		for weekday in range(7):
			rows = sorted(
				(window for window in self.windows if window.weekday == weekday),
				key=lambda window: window.start_time,
			)
			if any(left.end_time > right.start_time for left, right in zip(rows, rows[1:])):
				raise ValueError("Weekly working-hour ranges must not overlap")
		return self


class DateExceptionCreate(BaseModel):
	date: date
	start_time: time
	end_time: time
	is_available: bool

	@model_validator(mode="after")
	def valid_range(self):
		if self.date < date.today():
			raise ValueError("Availability exceptions must be for today or a future date")
		if (
			self.start_time.tzinfo
			or self.end_time.tzinfo
			or self.start_time >= self.end_time
		):
			raise ValueError("The time range must end after it starts")
		return self


def _doctor_profile(doctor: Doctor, db: Session) -> dict:
	weekly = (
		db.query(DoctorWeeklyAvailability)
		.filter_by(doctor_id=doctor.id)
		.order_by(DoctorWeeklyAvailability.weekday, DoctorWeeklyAvailability.start_time)
		.all()
	)
	return {
		"id": doctor.id,
		"name": doctor.name,
		"specialization": doctor.specialization,
		"hospital": doctor.hospital,
		"experience": doctor.experience,
		"consultation_fee": doctor.consultation_fee,
		"consultation_info": doctor.consultation_info,
		"profile_image_url": doctor.profile_image_url,
		"appointment_duration_minutes": doctor.appointment_duration_minutes or 30,
		"available_days": [
			WEEKDAYS[weekday]
			for weekday in sorted({row.weekday for row in weekly})
		],
		"weekly_schedule": [
			{
				"weekday": row.weekday,
				"weekday_name": WEEKDAYS[row.weekday],
				"start_time": row.start_time.isoformat(timespec="minutes"),
				"end_time": row.end_time.isoformat(timespec="minutes"),
			}
			for row in weekly
		],
	}


def _lock_doctor_schedule(db: Session, doctor_id: int) -> None:
	db.query(Doctor).filter_by(id=doctor_id).with_for_update().first()


@router.get("")
def list_doctors(
	specialization: str | None = Query(default=None, min_length=1),
	db: Session = Depends(get_db),
):
	query = db.query(Doctor)
	if specialization:
		terms = specialization_terms(specialization)
		query = query.filter(
			or_(*(Doctor.specialization.ilike(f"%{term}%") for term in terms))
		)
	return [_doctor_profile(doctor, db) for doctor in query.order_by(Doctor.name).all()]


@router.get("/availability")
def legacy_doctor_availability(
	appointment_date: date,
	doctor_id: int | None = None,
	specialization: str | None = Query(default=None, min_length=1),
	db: Session = Depends(get_db),
):
	doctors = db.query(Doctor)
	if doctor_id is not None:
		doctors = doctors.filter(Doctor.id == doctor_id)
	if specialization:
		terms = specialization_terms(specialization)
		doctors = doctors.filter(
			or_(*(Doctor.specialization.ilike(f"%{term}%") for term in terms))
		)
	return [
		slot
		for doctor in doctors.order_by(Doctor.name).all()
		for slot in slots_for_date(db, doctor, appointment_date)
	]


@router.get("/{doctor_id}/available-dates")
def doctor_available_dates(
	doctor_id: int,
	start_date: date | None = None,
	days: int = Query(default=60, ge=1, le=90),
	db: Session = Depends(get_db),
):
	doctor = db.get(Doctor, doctor_id)
	if doctor is None:
		raise HTTPException(status_code=404, detail="Doctor not found")
	return {
		"doctor_id": doctor.id,
		"dates": available_dates(db, doctor, start_date or date.today(), days),
	}


@router.get("/{doctor_id}/availability")
def doctor_day_availability(
	doctor_id: int,
	appointment_date: date,
	db: Session = Depends(get_db),
):
	doctor = db.get(Doctor, doctor_id)
	if doctor is None:
		raise HTTPException(status_code=404, detail="Doctor not found")
	return slots_for_date(db, doctor, appointment_date)


@router.get("/{doctor_id}")
def get_doctor_profile(doctor_id: int, db: Session = Depends(get_db)):
	doctor = db.get(Doctor, doctor_id)
	if doctor is None:
		raise HTTPException(status_code=404, detail="Doctor not found")
	return _doctor_profile(doctor, db)


@router.get("/me/availability/weekly")
def get_weekly_availability(
	db: Session = Depends(get_db),
	doctor: Doctor = Depends(get_current_doctor),
):
	return {
		"appointment_duration_minutes": doctor.appointment_duration_minutes or 30,
		"windows": _doctor_profile(doctor, db)["weekly_schedule"],
	}


@router.put("/me/availability/weekly")
def update_weekly_availability(
	body: WeeklyScheduleUpdate,
	db: Session = Depends(get_db),
	doctor: Doctor = Depends(get_current_doctor),
):
	_lock_doctor_schedule(db, doctor.id)
	db.query(DoctorWeeklyAvailability).filter_by(doctor_id=doctor.id).delete()
	doctor.appointment_duration_minutes = body.appointment_duration_minutes
	db.add_all(
		DoctorWeeklyAvailability(
			doctor_id=doctor.id,
			weekday=window.weekday,
			start_time=window.start_time,
			end_time=window.end_time,
		)
		for window in body.windows
	)
	db.commit()
	return {
		"appointment_duration_minutes": doctor.appointment_duration_minutes,
		"windows": _doctor_profile(doctor, db)["weekly_schedule"],
	}


@router.get("/me/availability/exceptions")
def list_date_exceptions(
	db: Session = Depends(get_db),
	doctor: Doctor = Depends(get_current_doctor),
):
	rows = (
		db.query(DoctorAvailability)
		.filter_by(doctor_id=doctor.id)
		.order_by(DoctorAvailability.date, DoctorAvailability.start_time)
		.all()
	)
	return [
		{
			"id": row.id,
			"date": row.date.isoformat(),
			"start_time": row.start_time.isoformat(timespec="minutes"),
			"end_time": row.end_time.isoformat(timespec="minutes"),
			"is_available": row.is_available,
		}
		for row in rows
	]


@router.post(
	"/me/availability/exceptions",
	status_code=status.HTTP_201_CREATED,
)
def add_date_exception(
	body: DateExceptionCreate,
	db: Session = Depends(get_db),
	doctor: Doctor = Depends(get_current_doctor),
):
	_lock_doctor_schedule(db, doctor.id)
	row = DoctorAvailability(doctor_id=doctor.id, **body.model_dump())
	db.add(row)
	db.commit()
	db.refresh(row)
	return {
		"id": row.id,
		"date": row.date.isoformat(),
		"start_time": row.start_time.isoformat(timespec="minutes"),
		"end_time": row.end_time.isoformat(timespec="minutes"),
		"is_available": row.is_available,
	}


@router.delete("/me/availability/exceptions/{exception_id}", status_code=204)
def delete_date_exception(
	exception_id: int,
	db: Session = Depends(get_db),
	doctor: Doctor = Depends(get_current_doctor),
):
	_lock_doctor_schedule(db, doctor.id)
	row = (
		db.query(DoctorAvailability)
		.filter_by(id=exception_id, doctor_id=doctor.id)
		.first()
	)
	if row is None:
		raise HTTPException(status_code=404, detail="Availability exception not found")
	db.delete(row)
	db.commit()
