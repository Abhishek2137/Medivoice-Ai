from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from ..database.models import (
	Appointment,
	Doctor,
	DoctorAvailability,
	DoctorWeeklyAvailability,
)


def slots_for_date(db: Session, doctor: Doctor, appointment_date: date) -> list[dict]:
	if appointment_date < date.today():
		return []

	exceptions = (
		db.query(DoctorAvailability)
		.filter_by(doctor_id=doctor.id, date=appointment_date)
		.order_by(DoctorAvailability.start_time)
		.all()
	)
	open_exceptions = [row for row in exceptions if row.is_available]
	if open_exceptions:
		windows = [
			(row.start_time, row.end_time)
			for row in open_exceptions
		]
	else:
		weekly = (
			db.query(DoctorWeeklyAvailability)
			.filter_by(doctor_id=doctor.id, weekday=appointment_date.weekday())
			.order_by(DoctorWeeklyAvailability.start_time)
			.all()
		)
		windows = [(row.start_time, row.end_time) for row in weekly]

	blocked = [(row.start_time, row.end_time) for row in exceptions if not row.is_available]
	appointments = (
		db.query(Appointment.appointment_time)
		.filter(
			Appointment.doctor_id == doctor.id,
			Appointment.appointment_date == appointment_date,
			Appointment.status == "confirmed",
		)
		.all()
	)
	duration = timedelta(minutes=doctor.appointment_duration_minutes or 30)
	now = datetime.now()
	slots: list[dict] = []
	slot_intervals: list[tuple[datetime, datetime]] = []
	occupied_times = [value for (value,) in appointments]
	for start, end in windows:
		candidate = datetime.combine(appointment_date, start)
		window_end = datetime.combine(appointment_date, end)
		while candidate + duration <= window_end:
			slot_end = candidate + duration
			if candidate > now and not any(
				candidate.time() < blocked_end and slot_end.time() > blocked_start
				for blocked_start, blocked_end in blocked
			) and not any(
				candidate < datetime.combine(appointment_date, occupied_time) + duration
				and slot_end > datetime.combine(appointment_date, occupied_time)
				for occupied_time in occupied_times
			) and not any(
				candidate < existing_end and slot_end > existing_start
				for existing_start, existing_end in slot_intervals
			):
				start_text = candidate.time().isoformat(timespec="minutes")
				slot_intervals.append((candidate, slot_end))
				slots.append(
					{
						"doctor_id": doctor.id,
						"doctor_name": doctor.name,
						"specialization": doctor.specialization,
						"hospital": doctor.hospital,
						"date": appointment_date.isoformat(),
						"start_time": start_text,
						"end_time": slot_end.time().isoformat(timespec="minutes"),
					}
				)
			candidate += duration
	return slots


def available_dates(
	db: Session, doctor: Doctor, start_date: date, days: int
) -> list[str]:
	dates = []
	for offset in range(days):
		current = start_date + timedelta(days=offset)
		if slots_for_date(db, doctor, current):
			dates.append(current.isoformat())
	return dates


def is_available_slot(
	db: Session, doctor_id: int, appointment_date: date, appointment_time: time
) -> bool:
	doctor = db.get(Doctor, doctor_id)
	if doctor is None:
		return False
	return any(
		slot["start_time"] == appointment_time.isoformat(timespec="minutes")
		for slot in slots_for_date(db, doctor, appointment_date)
	)
