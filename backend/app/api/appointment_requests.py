from datetime import date, datetime, time

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..database.models import (
	AppointmentNotification,
	AppointmentRequest,
	Doctor,
	Patient,
)
from ..services.appointment_request_service import (
	approve_request,
	create_appointment_request,
	deliver_notification,
	propose_alternative,
	reject_request,
	respond_to_proposal,
	retry_notifications,
)
from ..services.auth_service import get_current_doctor, get_current_patient

router = APIRouter(prefix="/appointment-requests", tags=["appointment requests"])


class CreateAppointmentRequest(BaseModel):
	doctor_id: int = Field(gt=0)
	requested_date: date
	requested_time: time
	reason: str | None = Field(default=None, max_length=2000)

	@field_validator("reason")
	@classmethod
	def normalize_reason(cls, value: str | None) -> str | None:
		if value is None:
			return None
		value = value.strip()
		return value or None


class RejectAppointmentRequest(BaseModel):
	reason: str = Field(min_length=3, max_length=1000)

	@field_validator("reason")
	@classmethod
	def reject_blank_reason(cls, value: str) -> str:
		value = value.strip()
		if len(value) < 3:
			raise ValueError("A rejection reason of at least 3 characters is required")
		return value


class CounterProposalRequest(BaseModel):
	proposed_date: date
	proposed_time: time


class ProposalResponse(BaseModel):
	decision: str = Field(pattern="^(accept|decline)$")


class AppointmentRequestResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	patient_id: int
	patient_name: str
	patient_email: str | None
	patient_phone: str | None
	doctor_id: int
	doctor_name: str
	appointment_id: int | None
	requested_date: date
	requested_time: time
	reason: str | None
	status: str
	proposed_date: date | None
	proposed_time: time | None
	rejection_reason: str | None
	decision_details: str | None
	created_at: datetime
	updated_at: datetime
	notification_status: list[str]

	@classmethod
	def from_request(cls, request: AppointmentRequest) -> "AppointmentRequestResponse":
		return cls(
			id=request.id,
			patient_id=request.patient_id,
			patient_name=request.patient.name,
			patient_email=request.patient.email,
			patient_phone=request.patient.phone,
			doctor_id=request.doctor_id,
			doctor_name=request.doctor.name,
			appointment_id=request.appointment_id,
			requested_date=request.requested_date,
			requested_time=request.requested_time,
			reason=request.reason,
			status=request.status,
			proposed_date=request.proposed_date,
			proposed_time=request.proposed_time,
			rejection_reason=request.rejection_reason,
			decision_details=request.decision_details,
			created_at=request.created_at,
			updated_at=request.updated_at,
			notification_status=[
				notification.status for notification in request.notifications
			],
		)


def _schedule_pending_notifications(
	background_tasks: BackgroundTasks,
	db: Session,
	request_id: int,
) -> None:
	rows = (
		db.query(AppointmentNotification)
		.filter_by(request_id=request_id, status="PENDING")
		.all()
	)
	for notification in rows:
		background_tasks.add_task(
			deliver_notification, notification.id, db.get_bind()
		)


@router.post("", response_model=AppointmentRequestResponse, status_code=201)
def create_request(
	body: CreateAppointmentRequest,
	background_tasks: BackgroundTasks,
	db: Session = Depends(get_db),
	patient: Patient = Depends(get_current_patient),
	idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=64),
) -> AppointmentRequestResponse:
	request = create_appointment_request(
		db,
		patient,
		body.doctor_id,
		body.requested_date,
		body.requested_time,
		body.reason,
		idempotency_key,
	)
	_schedule_pending_notifications(background_tasks, db, request.id)
	return AppointmentRequestResponse.from_request(request)


@router.get("/mine", response_model=list[AppointmentRequestResponse])
def list_patient_requests(
	db: Session = Depends(get_db),
	patient: Patient = Depends(get_current_patient),
) -> list[AppointmentRequestResponse]:
	requests = (
		db.query(AppointmentRequest)
		.filter_by(patient_id=patient.id)
		.order_by(AppointmentRequest.created_at.desc())
		.all()
	)
	return [AppointmentRequestResponse.from_request(request) for request in requests]


@router.get("/doctor/mine", response_model=list[AppointmentRequestResponse])
def list_doctor_requests(
	pending_only: bool = True,
	db: Session = Depends(get_db),
	doctor: Doctor = Depends(get_current_doctor),
) -> list[AppointmentRequestResponse]:
	query = db.query(AppointmentRequest).filter_by(doctor_id=doctor.id)
	if pending_only:
		query = query.filter(AppointmentRequest.status == "PENDING")
	requests = query.order_by(AppointmentRequest.created_at.asc()).all()
	return [AppointmentRequestResponse.from_request(request) for request in requests]


@router.post("/{request_id}/approve", response_model=AppointmentRequestResponse)
def approve(
	request_id: int,
	background_tasks: BackgroundTasks,
	db: Session = Depends(get_db),
	doctor: Doctor = Depends(get_current_doctor),
) -> AppointmentRequestResponse:
	request = approve_request(db, request_id, doctor.id)
	_schedule_pending_notifications(background_tasks, db, request.id)
	return AppointmentRequestResponse.from_request(request)


@router.post("/{request_id}/reject", response_model=AppointmentRequestResponse)
def reject(
	request_id: int,
	body: RejectAppointmentRequest,
	background_tasks: BackgroundTasks,
	db: Session = Depends(get_db),
	doctor: Doctor = Depends(get_current_doctor),
) -> AppointmentRequestResponse:
	request = reject_request(db, request_id, doctor.id, body.reason)
	_schedule_pending_notifications(background_tasks, db, request.id)
	return AppointmentRequestResponse.from_request(request)


@router.post(
	"/{request_id}/counter-propose", response_model=AppointmentRequestResponse
)
def counter_propose(
	request_id: int,
	body: CounterProposalRequest,
	background_tasks: BackgroundTasks,
	db: Session = Depends(get_db),
	doctor: Doctor = Depends(get_current_doctor),
) -> AppointmentRequestResponse:
	request = propose_alternative(
		db,
		request_id,
		doctor.id,
		body.proposed_date,
		body.proposed_time,
	)
	_schedule_pending_notifications(background_tasks, db, request.id)
	return AppointmentRequestResponse.from_request(request)


@router.post(
	"/{request_id}/proposal-response", response_model=AppointmentRequestResponse
)
def proposal_response(
	request_id: int,
	body: ProposalResponse,
	background_tasks: BackgroundTasks,
	db: Session = Depends(get_db),
	patient: Patient = Depends(get_current_patient),
) -> AppointmentRequestResponse:
	request = respond_to_proposal(db, request_id, patient.id, body.decision)
	_schedule_pending_notifications(background_tasks, db, request.id)
	return AppointmentRequestResponse.from_request(request)


@router.post(
	"/{request_id}/notifications/retry",
	status_code=202,
)
def retry_patient_notifications(
	request_id: int,
	background_tasks: BackgroundTasks,
	db: Session = Depends(get_db),
	patient: Patient = Depends(get_current_patient),
) -> dict[str, int]:
	notification_ids = retry_notifications(db, request_id, patient.id, None)
	for notification_id in notification_ids:
		background_tasks.add_task(
			deliver_notification, notification_id, db.get_bind()
		)
	return {"queued": len(notification_ids)}


@router.post(
	"/{request_id}/doctor-notifications/retry",
	status_code=202,
)
def retry_doctor_notifications(
	request_id: int,
	background_tasks: BackgroundTasks,
	db: Session = Depends(get_db),
	doctor: Doctor = Depends(get_current_doctor),
) -> dict[str, int]:
	notification_ids = retry_notifications(db, request_id, None, doctor.id)
	for notification_id in notification_ids:
		background_tasks.add_task(
			deliver_notification, notification_id, db.get_bind()
		)
	return {"queued": len(notification_ids)}
