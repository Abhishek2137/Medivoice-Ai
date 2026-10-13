from datetime import date, time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..database.models import Appointment, Patient
from ..database.schemas import AppointmentSearchRequest
from ..services.appointment_request_service import create_appointment_request
from ..services.auth_service import get_current_patient
from ..services.appointment_service import search_availability
from .appointment_requests import (
	AppointmentRequestResponse,
	_schedule_pending_notifications,
)

router = APIRouter(prefix="/appointment", tags=["appointments"])


class AppointmentBookRequest(BaseModel):
	patient_id: int | None = None
	doctor_id: int
	appointment_date: date
	appointment_time: time
	symptoms: str | None = None


def _create_request_from_legacy_endpoint(
	request: AppointmentBookRequest,
	background_tasks: BackgroundTasks,
	db: Session,
	patient: Patient,
) -> AppointmentRequestResponse:
	if request.patient_id is not None and request.patient_id != patient.id:
		raise HTTPException(status_code=403, detail="Cannot book for another patient")
	appointment_request = create_appointment_request(
		db,
		patient,
		request.doctor_id,
		request.appointment_date,
		request.appointment_time,
		request.symptoms,
	)
	_schedule_pending_notifications(background_tasks, db, appointment_request.id)
	return AppointmentRequestResponse.from_request(appointment_request)


@router.post("/search")
def search_appointments(
	request: AppointmentSearchRequest, db: Session = Depends(get_db)
):
	return [
		{
			"doctor_id": slot.doctor_id,
			"doctor_name": slot.doctor.name,
			"specialization": slot.doctor.specialization,
			"date": slot.date.isoformat(),
			"start_time": slot.start_time.isoformat(timespec="minutes"),
			"end_time": slot.end_time.isoformat(timespec="minutes"),
		}
		for slot in search_availability(db, request.appointment_date, request.doctor_id)
	]


@router.post(
	"/book", response_model=AppointmentRequestResponse, status_code=201
)
def create_appointment(
	request: AppointmentBookRequest,
	background_tasks: BackgroundTasks,
	db: Session = Depends(get_db),
	patient: Patient = Depends(get_current_patient),
) -> AppointmentRequestResponse:
	return _create_request_from_legacy_endpoint(
		request, background_tasks, db, patient
	)


@router.get("/patient/{patient_id}")
def patient_appointments(
	patient_id: int,
	db: Session = Depends(get_db),
	patient: Patient = Depends(get_current_patient),
):
	if patient_id != patient.id:
		raise HTTPException(status_code=404, detail="Appointment list not found")
	return db.query(Appointment).filter_by(patient_id=patient_id).order_by(
		Appointment.appointment_date, Appointment.appointment_time
	).all()


@router.get("/mine")
def my_appointments(
	appointment_date: date | None = None,
	doctor_id: int | None = None,
	status: str | None = Query(default=None, min_length=1),
	db: Session = Depends(get_db),
	patient: Patient = Depends(get_current_patient),
):
	query = db.query(Appointment).filter_by(patient_id=patient.id)
	if appointment_date is not None:
		query = query.filter(Appointment.appointment_date == appointment_date)
	if doctor_id is not None:
		query = query.filter(Appointment.doctor_id == doctor_id)
	if status is not None:
		query = query.filter(Appointment.status == status)
	return query.order_by(
		Appointment.appointment_date, Appointment.appointment_time
	).all()


@router.delete("/{appointment_id}")
def cancel_appointment(
	appointment_id: int,
	db: Session = Depends(get_db),
	patient: Patient = Depends(get_current_patient),
):
	appointment = db.query(Appointment).filter_by(
		id=appointment_id, patient_id=patient.id
	).first()
	if appointment is None:
		raise HTTPException(status_code=404, detail="Appointment not found")
	if appointment.status != "confirmed":
		raise HTTPException(status_code=409, detail="This appointment cannot be cancelled")
	appointment.status = "cancelled"
	db.commit()
	db.refresh(appointment)
	return appointment


class RescheduleRequest(BaseModel):
	appointment_date: date
	appointment_time: str


@router.put("/{appointment_id}/reschedule")
def reschedule_appointment(
	appointment_id: int,
	request: RescheduleRequest,
	db: Session = Depends(get_db),
	patient: Patient = Depends(get_current_patient),
):
	appointment = db.query(Appointment).filter_by(
		id=appointment_id, patient_id=patient.id
	).first()
	if appointment is None:
		raise HTTPException(status_code=404, detail="Appointment not found")
	raise HTTPException(
		status_code=409,
		detail="Rescheduling requires a new doctor-approved appointment request",
	)
