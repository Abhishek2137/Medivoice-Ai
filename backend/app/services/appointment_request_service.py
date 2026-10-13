import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from ..database.models import (
	Appointment,
	AppointmentNotification,
	AppointmentRequest,
	Doctor,
	Patient,
)
from .availability_service import is_available_slot
from .notification_service import send_appointment_notification

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
	return datetime.now(timezone.utc).replace(tzinfo=None)


ACTIVE_REQUEST_STATUSES = (
	"PENDING",
	"APPROVED",
	"COUNTER_PROPOSED",
	"CONFIRMED",
)


def validate_future_slot(appointment_date: date, appointment_time: time) -> None:
	if appointment_time.tzinfo is not None:
		raise HTTPException(status_code=422, detail="Appointment time must not include a timezone")
	if datetime.combine(appointment_date, appointment_time) <= datetime.now():
		raise HTTPException(
			status_code=422, detail="Choose an appointment date and time in the future"
		)


def create_appointment_request(
	db: Session,
	patient: Patient,
	doctor_id: int,
	requested_date: date,
	requested_time: time,
	reason: str | None,
	idempotency_key: str | None = None,
) -> AppointmentRequest:
	validate_future_slot(requested_date, requested_time)
	if db.get(Doctor, doctor_id) is None:
		raise HTTPException(status_code=404, detail="Doctor not found")

	if idempotency_key:
		existing = (
			db.query(AppointmentRequest)
			.filter_by(patient_id=patient.id, idempotency_key=idempotency_key)
			.first()
		)
		if existing is not None:
			if (
				existing.doctor_id != doctor_id
				or existing.requested_date != requested_date
				or existing.requested_time != requested_time
				or existing.reason != reason
			):
				raise HTTPException(
					status_code=409,
					detail="This idempotency key was already used for another request",
				)
			return existing
	confirmed_appointment = (
		db.query(Appointment)
		.filter(
			Appointment.doctor_id == doctor_id,
			Appointment.appointment_date == requested_date,
			Appointment.appointment_time == requested_time,
			Appointment.status == "confirmed",
		)
		.first()
	)
	if confirmed_appointment is not None:
		raise HTTPException(
			status_code=409,
			detail="This time is already confirmed. Please choose another preferred time.",
		)
	if not is_available_slot(db, doctor_id, requested_date, requested_time):
		raise HTTPException(
			status_code=409,
			detail="That time is not an available appointment slot. Choose a listed opening.",
		)
	existing_active = (
		db.query(AppointmentRequest)
		.filter(
			AppointmentRequest.patient_id == patient.id,
			AppointmentRequest.doctor_id == doctor_id,
			AppointmentRequest.requested_date == requested_date,
			AppointmentRequest.requested_time == requested_time,
			AppointmentRequest.status.in_(ACTIVE_REQUEST_STATUSES),
		)
		.first()
	)
	if existing_active is not None:
		raise HTTPException(
			status_code=409,
			detail="You already have an active request for this doctor at this time",
		)

	request = AppointmentRequest(
		patient_id=patient.id,
		doctor_id=doctor_id,
		requested_date=requested_date,
		requested_time=requested_time,
		reason=reason,
		status="PENDING",
		idempotency_key=idempotency_key,
	)
	db.add(request)
	try:
		db.flush()
		doctor = db.get(Doctor, doctor_id)
		if doctor is None or not doctor.email or not doctor.email.strip():
			db.rollback()
			raise HTTPException(
				status_code=409,
				detail="This doctor does not have a registered email address for requests",
			)
		db.add(
			AppointmentNotification(
				request_id=request.id,
				notification_type="doctor_request",
				recipient=doctor.email.strip(),
				status="PENDING",
			)
		)
		db.commit()
	except IntegrityError as error:
		db.rollback()
		raise HTTPException(
			status_code=409,
			detail="An active request already exists for this doctor and time",
		) from error
	db.refresh(request)
	return request


def _create_confirmed_appointment(
	db: Session, request: AppointmentRequest, appointment_date: date, appointment_time: time
) -> Appointment:
	doctor = (
		db.query(Doctor)
		.filter(Doctor.id == request.doctor_id)
		.with_for_update()
		.first()
	)
	if doctor is None:
		raise HTTPException(status_code=404, detail="Doctor not found")
	conflict = (
		db.query(Appointment)
		.filter(
			Appointment.doctor_id == request.doctor_id,
			Appointment.appointment_date == appointment_date,
			Appointment.appointment_time == appointment_time,
			Appointment.status == "confirmed",
		)
		.first()
	)
	if conflict is not None:
		raise HTTPException(
			status_code=409,
			detail="That time has already been confirmed. Please suggest another time.",
		)
	if not is_available_slot(db, request.doctor_id, appointment_date, appointment_time):
		raise HTTPException(
			status_code=409,
			detail="That time is no longer available in the doctor's schedule.",
		)

	appointment = Appointment(
		patient_id=request.patient_id,
		doctor_id=request.doctor_id,
		appointment_date=appointment_date,
		appointment_time=appointment_time,
		status="confirmed",
		symptoms=request.reason,
	)
	db.add(appointment)
	db.flush()
	request.appointment_id = appointment.id
	return appointment


def _queue_patient_notification(
	db: Session, request: AppointmentRequest, notification_type: str
) -> None:
	patient = db.get(Patient, request.patient_id)
	if patient is None or not patient.email:
		return
	db.add(
		AppointmentNotification(
			request_id=request.id,
			notification_type=notification_type,
			recipient=patient.email,
			status="PENDING",
		)
	)


def _ensure_decision_is_pending(request: AppointmentRequest) -> bool:
	if request.status == "PENDING":
		return True
	if request.status in {"APPROVED", "REJECTED", "COUNTER_PROPOSED", "CONFIRMED"}:
		return False
	raise HTTPException(status_code=409, detail="This request cannot be decided")


def approve_request(db: Session, request_id: int, doctor_id: int) -> AppointmentRequest:
	request = (
		db.query(AppointmentRequest)
		.filter_by(id=request_id, doctor_id=doctor_id)
		.with_for_update()
		.first()
	)
	if request is None:
		raise HTTPException(status_code=404, detail="Appointment request not found")
	if not _ensure_decision_is_pending(request):
		if request.status == "APPROVED":
			return request
		raise HTTPException(status_code=409, detail="This request has already been handled")
	try:
		_create_confirmed_appointment(
			db, request, request.requested_date, request.requested_time
		)
		request.status = "APPROVED"
		request.decision_details = "Approved by the doctor; appointment confirmed."
		request.decided_at = _utc_now()
		_queue_patient_notification(db, request, "patient_approved")
		db.commit()
	except IntegrityError as error:
		db.rollback()
		raise HTTPException(
			status_code=409,
			detail="That time has already been confirmed. Please suggest another time.",
		) from error
	except OperationalError as error:
		db.rollback()
		if (
			db.query(Appointment)
			.filter(
				Appointment.doctor_id == request.doctor_id,
				Appointment.appointment_date == request.requested_date,
				Appointment.appointment_time == request.requested_time,
				Appointment.status == "confirmed",
			)
			.first()
			is None
		):
			raise
		raise HTTPException(
			status_code=409,
			detail="That time has already been confirmed. Please suggest another time.",
		) from error
	db.refresh(request)
	return request


def reject_request(
	db: Session, request_id: int, doctor_id: int, reason: str
) -> AppointmentRequest:
	request = (
		db.query(AppointmentRequest)
		.filter_by(id=request_id, doctor_id=doctor_id)
		.with_for_update()
		.first()
	)
	if request is None:
		raise HTTPException(status_code=404, detail="Appointment request not found")
	if not _ensure_decision_is_pending(request):
		if request.status == "REJECTED" and request.rejection_reason == reason:
			return request
		raise HTTPException(status_code=409, detail="This request has already been handled")

	request.status = "REJECTED"
	request.rejection_reason = reason
	request.decision_details = f"Rejected by the doctor: {reason}"
	request.decided_at = _utc_now()
	_queue_patient_notification(db, request, "patient_rejected")
	db.commit()
	db.refresh(request)
	return request


def propose_alternative(
	db: Session,
	request_id: int,
	doctor_id: int,
	proposed_date: date,
	proposed_time: time,
) -> AppointmentRequest:
	validate_future_slot(proposed_date, proposed_time)
	request = (
		db.query(AppointmentRequest)
		.filter_by(id=request_id, doctor_id=doctor_id)
		.with_for_update()
		.first()
	)
	if request is None:
		raise HTTPException(status_code=404, detail="Appointment request not found")
	if not _ensure_decision_is_pending(request):
		if (
			request.status == "COUNTER_PROPOSED"
			and request.proposed_date == proposed_date
			and request.proposed_time == proposed_time
		):
			return request
		raise HTTPException(status_code=409, detail="This request has already been handled")
	if not is_available_slot(
		db, request.doctor_id, proposed_date, proposed_time
	):
		raise HTTPException(
			status_code=409,
			detail="The proposed time is not an available slot in your schedule.",
		)

	request.status = "COUNTER_PROPOSED"
	request.proposed_date = proposed_date
	request.proposed_time = proposed_time
	request.decision_details = (
		f"The doctor proposed {proposed_date.isoformat()} at "
		f"{proposed_time.strftime('%H:%M')}."
	)
	request.decided_at = _utc_now()
	_queue_patient_notification(db, request, "patient_counter_proposed")
	db.commit()
	db.refresh(request)
	return request


def respond_to_proposal(
	db: Session, request_id: int, patient_id: int, decision: str
) -> AppointmentRequest:
	request = (
		db.query(AppointmentRequest)
		.filter_by(id=request_id, patient_id=patient_id)
		.with_for_update()
		.first()
	)
	if request is None:
		raise HTTPException(status_code=404, detail="Appointment request not found")
	if request.status != "COUNTER_PROPOSED":
		if decision == "accept" and request.status == "CONFIRMED":
			return request
		if decision == "decline" and request.status == "REJECTED":
			return request
		raise HTTPException(status_code=409, detail="There is no active time proposal")
	if decision == "decline":
		request.status = "REJECTED"
		request.decision_details = "The patient declined the proposed time."
		request.decided_at = _utc_now()
		db.commit()
		db.refresh(request)
		return request

	if request.proposed_date is None or request.proposed_time is None:
		raise HTTPException(status_code=409, detail="The proposed time is incomplete")
	validate_future_slot(request.proposed_date, request.proposed_time)
	if not is_available_slot(
		db, request.doctor_id, request.proposed_date, request.proposed_time
	):
		raise HTTPException(
			status_code=409,
			detail="The proposed time is no longer available. Contact the doctor.",
		)
	try:
		_create_confirmed_appointment(
			db, request, request.proposed_date, request.proposed_time
		)
		request.status = "CONFIRMED"
		request.decision_details = (
			"The patient accepted the doctor's proposed time; appointment confirmed."
		)
		request.decided_at = _utc_now()
		db.commit()
	except IntegrityError as error:
		db.rollback()
		raise HTTPException(
			status_code=409,
			detail="That proposed time has already been confirmed. Contact the doctor.",
		) from error
	except OperationalError as error:
		db.rollback()
		if (
			db.query(Appointment)
			.filter(
				Appointment.doctor_id == request.doctor_id,
				Appointment.appointment_date == request.proposed_date,
				Appointment.appointment_time == request.proposed_time,
				Appointment.status == "confirmed",
			)
			.first()
			is None
		):
			raise
		raise HTTPException(
			status_code=409,
			detail="That proposed time has already been confirmed. Contact the doctor.",
		) from error
	db.refresh(request)
	return request


def deliver_notification(notification_id: int, bind) -> None:
	session_factory: Callable = sessionmaker(bind=bind, expire_on_commit=False)
	with session_factory() as db:
		stale_sending_before = _utc_now() - timedelta(minutes=5)
		claimed = (
			db.query(AppointmentNotification)
			.filter(
				AppointmentNotification.id == notification_id,
				or_(
					AppointmentNotification.status.in_(("PENDING", "FAILED")),
					and_(
						AppointmentNotification.status == "SENDING",
						AppointmentNotification.updated_at < stale_sending_before,
					),
				),
			)
			.update(
				{
					"status": "SENDING",
					"attempt_count": AppointmentNotification.attempt_count + 1,
					"updated_at": _utc_now(),
				},
				synchronize_session=False,
			)
		)
		if not claimed:
			return
		db.commit()
		notification = db.get(AppointmentNotification, notification_id)
		if notification is None:
			return
		request = db.get(AppointmentRequest, notification.request_id)
		if request is None:
			notification.status = "FAILED"
			notification.last_error = "request_not_found"
			db.commit()
			return
		try:
			send_appointment_notification(notification, request)
		except Exception as error:
			notification.status = "FAILED"
			notification.last_error = type(error).__name__[:80]
			db.commit()
			logger.error(
				"Appointment notification %s delivery failed (%s)",
				notification.id,
				type(error).__name__,
			)
			return
		notification.status = "SENT"
		notification.last_error = None
		notification.sent_at = _utc_now()
		db.commit()


def retry_notifications(
	db: Session, request_id: int, patient_id: int | None, doctor_id: int | None
) -> list[int]:
	request = db.get(AppointmentRequest, request_id)
	if request is None or (
		request.patient_id != patient_id and request.doctor_id != doctor_id
	):
		raise HTTPException(status_code=404, detail="Appointment request not found")
	rows = (
		db.query(AppointmentNotification)
		.filter(
			AppointmentNotification.request_id == request_id,
			or_(
				AppointmentNotification.status.in_(("PENDING", "FAILED")),
				and_(
					AppointmentNotification.status == "SENDING",
					AppointmentNotification.updated_at
					< _utc_now() - timedelta(minutes=5),
				),
			),
		)
		.all()
	)
	return [row.id for row in rows]
