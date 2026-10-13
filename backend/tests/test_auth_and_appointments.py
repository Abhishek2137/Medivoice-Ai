from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from threading import Barrier

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import get_db
from app.database.models import (
	Appointment,
	AppointmentNotification,
	AppointmentRequest,
	Base,
	Doctor,
	DoctorCredential,
	DoctorAvailability,
	DoctorWeeklyAvailability,
	Patient,
	PatientCredential,
)
from app.main import app
from app.services.auth_service import create_access_token, hash_password
from app.services.appointment_request_service import approve_request
import app.database.database as database_module


@pytest.fixture
def client(monkeypatch):
	monkeypatch.setenv("APP_SECRET_KEY", "test-only-signing-secret-at-least-32-chars")
	engine = create_engine(
		"sqlite://",
		connect_args={"check_same_thread": False},
		poolclass=StaticPool,
	)
	Base.metadata.create_all(bind=engine)
	session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

	def override_get_db():
		db = session_factory()
		try:
			yield db
		finally:
			db.close()

	app.dependency_overrides[get_db] = override_get_db
	app.state.test_session_factory = session_factory
	with TestClient(app) as test_client:
		yield test_client
	app.dependency_overrides.clear()
	del app.state.test_session_factory
	Base.metadata.drop_all(bind=engine)
	engine.dispose()


def register(client, name, email):
	response = client.post(
		"/auth/register",
		json={"name": name, "email": email, "password": "correct-horse-battery"},
	)
	assert response.status_code == 201
	return response.json()


def auth_headers(auth_response):
	return {"Authorization": f"Bearer {auth_response['access_token']}"}


def add_doctor(db, email="doctor@example.com", name="Dr Rao", with_schedule=True):
	doctor = Doctor(
		name=name,
		email=email,
		specialization="Cardiology",
		hospital="City Clinic",
		available_days="Mon,Tue",
	)
	db.add(doctor)
	db.flush()
	db.add(
		DoctorCredential(
			doctor_id=doctor.id,
			email=email,
			password_hash=hash_password("doctor-secure-password"),
		)
	)
	if with_schedule:
		doctor.appointment_duration_minutes = 15
		db.add_all(
			DoctorWeeklyAvailability(
				doctor_id=doctor.id,
				weekday=weekday,
				start_time=time(0, 0),
				end_time=time(23, 59),
			)
			for weekday in range(7)
		)
	db.commit()
	return doctor.id


def test_register_login_hash_password_and_protect_account(client):
	registered = register(client, "Asha Patel", "ASHA@example.com")
	assert registered["patient"]["email"] == "asha@example.com"

	account = client.get("/auth/me", headers=auth_headers(registered))
	assert account.status_code == 200
	assert account.json()["name"] == "Asha Patel"
	assert account.json()["role"] == "patient"

	login = client.post(
		"/auth/login",
		json={"email": "asha@example.com", "password": "correct-horse-battery"},
	)
	assert login.status_code == 200
	assert login.json()["patient"]["id"] == registered["patient"]["id"]

	invalid_login = client.post(
		"/auth/login",
		json={"email": "asha@example.com", "password": "wrong-password"},
	)
	assert invalid_login.status_code == 401

	db = client.app.state.test_session_factory()
	try:
		credential = db.query(PatientCredential).filter_by(email="asha@example.com").one()
		assert credential.password_hash != "correct-horse-battery"
		assert db.query(Patient).filter_by(id=credential.patient_id).count() == 1
	finally:
		db.close()


def test_duplicate_registration_is_rejected(client):
	register(client, "Asha", "asha@example.com")
	response = client.post(
		"/auth/register",
		json={"name": "Another Asha", "email": "ASHA@example.com", "password": "correct-horse-battery"},
	)
	assert response.status_code == 409


def test_appointments_require_authentication_and_are_scoped_to_owner(client):
	first_patient = register(client, "Asha", "asha@example.com")
	second_patient = register(client, "Ravi", "ravi@example.com")
	db = client.app.state.test_session_factory()
	doctor_id = add_doctor(db)
	request_date = date.today() + timedelta(days=2)
	db.close()

	unauthorized = client.post(
		"/appointment-requests",
		json={
			"patient_id": first_patient["patient"]["id"],
			"doctor_id": doctor_id,
			"requested_date": request_date.isoformat(),
			"requested_time": "09:00",
		},
	)
	assert unauthorized.status_code == 401
	assert client.get("/appointment/mine").status_code == 401

	booked = client.post(
		"/appointment-requests",
		headers=auth_headers(first_patient),
		json={
			"doctor_id": doctor_id,
			"requested_date": request_date.isoformat(),
			"requested_time": "09:00",
		},
	)
	assert booked.status_code == 201
	request_id = booked.json()["id"]
	assert booked.json()["status"] == "PENDING"
	assert booked.json()["appointment_id"] is None
	assert booked.json()["patient_id"] == first_patient["patient"]["id"]

	first_list = client.get("/appointment/mine", headers=auth_headers(first_patient))
	second_list = client.get("/appointment/mine", headers=auth_headers(second_patient))
	assert first_list.json() == []
	assert second_list.json() == []
	assert client.get(
		f"/appointment/patient/{first_patient['patient']['id']}",
		headers=auth_headers(second_patient),
	).status_code == 404

	first_requests = client.get(
		"/appointment-requests/mine", headers=auth_headers(first_patient)
	)
	second_requests = client.get(
		"/appointment-requests/mine", headers=auth_headers(second_patient)
	)
	assert [row["id"] for row in first_requests.json()] == [request_id]
	assert second_requests.json() == []
	assert client.post(
		f"/appointment-requests/{request_id}/approve",
		headers=auth_headers(second_patient),
	).status_code == 401


def test_request_on_weekly_availability_is_pending_and_idempotent(client, monkeypatch):
	registered = register(client, "Asha", "asha@example.com")
	monkeypatch.setattr(
		"app.services.appointment_request_service.send_appointment_notification",
		lambda notification, request: None,
	)
	db = client.app.state.test_session_factory()
	doctor_id = add_doctor(db)
	db.close()
	request_date = date.today() + timedelta(days=14)
	payload = {
		"doctor_id": doctor_id,
		"requested_date": request_date.isoformat(),
		"requested_time": "13:15",
		"reason": "Routine consultation",
	}

	unauthorized = client.post("/appointment-requests", json=payload)
	assert unauthorized.status_code == 401

	first = client.post(
		"/appointment-requests",
		headers={**auth_headers(registered), "Idempotency-Key": "request-once"},
		json=payload,
	)
	assert first.status_code == 201
	assert first.json()["status"] == "PENDING"
	assert first.json()["appointment_id"] is None
	replay = client.post(
		"/appointment-requests",
		headers={**auth_headers(registered), "Idempotency-Key": "request-once"},
		json=payload,
	)
	assert replay.status_code == 201
	assert replay.json()["id"] == first.json()["id"]
	duplicate = client.post(
		"/appointment-requests", headers=auth_headers(registered), json=payload
	)
	assert duplicate.status_code == 409
	past = client.post(
		"/appointment-requests",
		headers=auth_headers(registered),
		json={
			**payload,
			"requested_date": (date.today() - timedelta(days=1)).isoformat(),
		},
	)
	assert past.status_code == 422

	db = client.app.state.test_session_factory()
	try:
		assert db.query(Appointment).count() == 0
		row = db.query(AppointmentRequest).one()
		assert row.requested_date == request_date
		assert row.reason == "Routine consultation"
		assert row.status == "PENDING"
		notification = db.query(AppointmentNotification).one()
		assert notification.notification_type == "doctor_request"
		assert notification.status == "SENT"
	finally:
		db.close()


def test_doctor_approval_conflict_and_idempotency(client, monkeypatch):
	first_patient = register(client, "Asha", "asha@example.com")
	second_patient = register(client, "Ravi", "ravi@example.com")
	monkeypatch.setattr(
		"app.services.appointment_request_service.send_appointment_notification",
		lambda notification, request: None,
	)
	db = client.app.state.test_session_factory()
	doctor_id = add_doctor(db)
	db.close()
	request_date = date.today() + timedelta(days=10)
	payload = {
		"doctor_id": doctor_id,
		"requested_date": request_date.isoformat(),
		"requested_time": "11:00",
	}
	first = client.post(
		"/appointment-requests", headers=auth_headers(first_patient), json=payload
	).json()
	second = client.post(
		"/appointment-requests", headers=auth_headers(second_patient), json=payload
	).json()
	doctor_login = client.post(
		"/auth/doctor/login",
		json={"email": "doctor@example.com", "password": "doctor-secure-password"},
	)
	assert doctor_login.status_code == 200
	doctor_headers = auth_headers(doctor_login.json())
	assert client.get("/appointment-requests/doctor/mine").status_code == 401
	assert len(
		client.get(
			"/appointment-requests/doctor/mine", headers=doctor_headers
		).json()
	) == 2
	db = client.app.state.test_session_factory()
	add_doctor(db, "other-doctor@example.com", "Dr Mehta")
	db.close()
	other_doctor = client.post(
		"/auth/doctor/login",
		json={
			"email": "other-doctor@example.com",
			"password": "doctor-secure-password",
		},
	).json()
	other_headers = auth_headers(other_doctor)
	assert client.get(
		"/appointment-requests/doctor/mine", headers=other_headers
	).json() == []
	assert client.post(
		f"/appointment-requests/{first['id']}/approve", headers=other_headers
	).status_code == 404

	approved = client.post(
		f"/appointment-requests/{first['id']}/approve", headers=doctor_headers
	)
	assert approved.status_code == 200
	assert approved.json()["status"] == "APPROVED"
	assert approved.json()["appointment_id"] is not None
	replayed = client.post(
		f"/appointment-requests/{first['id']}/approve", headers=doctor_headers
	)
	assert replayed.status_code == 200
	assert replayed.json()["appointment_id"] == approved.json()["appointment_id"]

	conflict = client.post(
		f"/appointment-requests/{second['id']}/approve", headers=doctor_headers
	)
	assert conflict.status_code == 409
	assert "already been confirmed" in conflict.json()["detail"]
	third_patient = register(client, "Priya", "priya@example.com")
	new_request_conflict = client.post(
		"/appointment-requests",
		headers=auth_headers(third_patient),
		json=payload,
	)
	assert new_request_conflict.status_code == 409
	assert "choose another preferred time" in new_request_conflict.json()["detail"]
	db = client.app.state.test_session_factory()
	try:
		assert db.query(Appointment).filter_by(status="confirmed").count() == 1
		assert db.get(AppointmentRequest, second["id"]).status == "PENDING"
	finally:
		db.close()


def test_rejection_and_alternative_proposal_patient_response(client, monkeypatch):
	patient = register(client, "Asha", "asha@example.com")
	monkeypatch.setattr(
		"app.services.appointment_request_service.send_appointment_notification",
		lambda notification, request: None,
	)
	db = client.app.state.test_session_factory()
	doctor_id = add_doctor(db)
	db.close()
	doctor_auth = client.post(
		"/auth/doctor/login",
		json={"email": "doctor@example.com", "password": "doctor-secure-password"},
	).json()
	doctor_headers = auth_headers(doctor_auth)
	request_date = date.today() + timedelta(days=4)
	request = client.post(
		"/appointment-requests",
		headers=auth_headers(patient),
		json={
			"doctor_id": doctor_id,
			"requested_date": request_date.isoformat(),
			"requested_time": "09:00",
		},
	).json()
	proposed_date = date.today() + timedelta(days=8)
	proposed = client.post(
		f"/appointment-requests/{request['id']}/counter-propose",
		headers=doctor_headers,
		json={"proposed_date": proposed_date.isoformat(), "proposed_time": "10:30"},
	)
	assert proposed.status_code == 200
	assert proposed.json()["status"] == "COUNTER_PROPOSED"
	assert proposed.json()["proposed_date"] == proposed_date.isoformat()
	accepted = client.post(
		f"/appointment-requests/{request['id']}/proposal-response",
		headers=auth_headers(patient),
		json={"decision": "accept"},
	)
	assert accepted.status_code == 200
	assert accepted.json()["status"] == "CONFIRMED"
	assert accepted.json()["appointment_id"] is not None
	assert client.post(
		f"/appointment-requests/{request['id']}/proposal-response",
		headers=auth_headers(patient),
		json={"decision": "accept"},
	).json()["appointment_id"] == accepted.json()["appointment_id"]

	rejected_request = client.post(
		"/appointment-requests",
		headers=auth_headers(patient),
		json={
			"doctor_id": doctor_id,
			"requested_date": (date.today() + timedelta(days=5)).isoformat(),
			"requested_time": "09:30",
		},
	).json()
	rejected = client.post(
		f"/appointment-requests/{rejected_request['id']}/reject",
		headers=doctor_headers,
		json={"reason": "The doctor is unavailable at that time"},
	)
	assert rejected.status_code == 200
	assert rejected.json()["status"] == "REJECTED"
	assert rejected.json()["rejection_reason"] == "The doctor is unavailable at that time"
	assert client.get(
		"/appointment-requests/doctor/mine", headers=doctor_headers
	).json() == []


def test_failed_doctor_notification_is_retained_and_retryable(client, monkeypatch):
	patient = register(client, "Asha", "asha@example.com")
	db = client.app.state.test_session_factory()
	doctor_id = add_doctor(db)
	db.close()

	def fail_delivery(notification, request):
		raise OSError("smtp unavailable")

	monkeypatch.setattr(
		"app.services.appointment_request_service.send_appointment_notification",
		fail_delivery,
	)
	response = client.post(
		"/appointment-requests",
		headers=auth_headers(patient),
		json={
			"doctor_id": doctor_id,
			"requested_date": (date.today() + timedelta(days=3)).isoformat(),
			"requested_time": "15:00",
		},
	)
	assert response.status_code == 201
	request_id = response.json()["id"]
	assert response.json()["status"] == "PENDING"
	request_history = client.get(
		"/appointment-requests/mine", headers=auth_headers(patient)
	)
	assert "FAILED" in request_history.json()[0]["notification_status"]

	monkeypatch.setattr(
		"app.services.appointment_request_service.send_appointment_notification",
		lambda notification, request: None,
	)
	retried = client.post(
		f"/appointment-requests/{request_id}/notifications/retry",
		headers=auth_headers(patient),
	)
	assert retried.status_code == 202
	assert retried.json()["queued"] == 1
	db = client.app.state.test_session_factory()
	try:
		assert db.query(AppointmentRequest).count() == 1
		assert db.query(AppointmentNotification).one().status == "SENT"
		assert db.query(AppointmentNotification).one().attempt_count == 2
	finally:
		db.close()


def test_confirmed_appointment_slot_is_database_unique(client):
	db = client.app.state.test_session_factory()
	doctor = Doctor(name="Dr Rao", email="doctor@example.com")
	db.add(doctor)
	db.flush()
	patients = [
		Patient(name="Asha", email="asha@example.com"),
		Patient(name="Ravi", email="ravi@example.com"),
	]
	db.add_all(patients)
	db.flush()
	slot = {
		"doctor_id": doctor.id,
		"appointment_date": date.today() + timedelta(days=2),
		"appointment_time": time(11, 0),
		"status": "confirmed",
	}
	db.add(Appointment(patient_id=patients[0].id, **slot))
	db.commit()
	db.add(Appointment(patient_id=patients[1].id, **slot))
	with pytest.raises(IntegrityError):
		db.commit()
	db.rollback()
	assert db.query(Appointment).filter_by(status="confirmed").count() == 1
	db.close()


def test_concurrent_approvals_cannot_confirm_the_same_slot(tmp_path, monkeypatch):
	engine = create_engine(
		f"sqlite:///{(tmp_path / 'concurrent-approvals.db').as_posix()}",
		connect_args={"check_same_thread": False, "timeout": 10},
	)
	Base.metadata.create_all(bind=engine)
	session_factory = sessionmaker(bind=engine, expire_on_commit=False)
	with session_factory() as db:
		doctor = Doctor(name="Dr Rao", email="doctor@example.com")
		doctor.appointment_duration_minutes = 15
		patients = [
			Patient(name="Asha", email="asha@example.com"),
			Patient(name="Ravi", email="ravi@example.com"),
		]
		db.add(doctor)
		db.add_all(patients)
		db.flush()
		db.add_all(
			DoctorWeeklyAvailability(
				doctor_id=doctor.id,
				weekday=weekday,
				start_time=time(9, 0),
				end_time=time(17, 0),
			)
			for weekday in range(7)
		)
		requests = [
			AppointmentRequest(
				patient_id=patient.id,
				doctor_id=doctor.id,
				requested_date=date.today() + timedelta(days=6),
				requested_time=time(12, 0),
				status="PENDING",
			)
			for patient in patients
		]
		db.add_all(requests)
		db.commit()
		doctor_id = doctor.id
		request_ids = [request.id for request in requests]

	barrier = Barrier(2)
	import app.services.appointment_request_service as request_service

	original_create = request_service._create_confirmed_appointment

	def synchronize_slot_check(db, request, appointment_date, appointment_time):
		barrier.wait(timeout=5)
		return original_create(db, request, appointment_date, appointment_time)

	monkeypatch.setattr(
		request_service, "_create_confirmed_appointment", synchronize_slot_check
	)

	def decide(request_id):
		with session_factory() as db:
			try:
				return approve_request(db, request_id, doctor_id).status
			except HTTPException as error:
				return error.status_code

	with ThreadPoolExecutor(max_workers=2) as executor:
		results = list(executor.map(decide, request_ids))
	assert sorted(map(str, results)) == ["409", "APPROVED"]
	with session_factory() as db:
		assert db.query(Appointment).filter_by(status="confirmed").count() == 1
	engine.dispose()


def test_doctor_directory_is_public_and_patient_voice_state_is_protected(client):
	db = client.app.state.test_session_factory()
	doctor = Doctor(
		name="Dr Rao",
		specialization="Cardiology",
		hospital="City Clinic",
		available_days="Mon,Tue",
	)
	db.add(doctor)
	db.flush()
	db.add(
		DoctorAvailability(
			doctor_id=doctor.id,
			date=date.today() + timedelta(days=1),
			start_time=time(9, 0),
			end_time=time(9, 30),
			is_available=True,
		)
	)
	db.commit()
	doctor_id = doctor.id
	available_date = date.today() + timedelta(days=1)
	db.close()

	doctor = client.get("/doctors")
	assert doctor.status_code == 200
	assert doctor.json()[0]["specialization"] == "Cardiology"
	assert doctor.json()[0]["available_days"] == []
	assert client.get("/doctors", params={"specialization": "cardiologist"}).json()
	slots = client.get(
		"/doctors/availability",
		params={"appointment_date": available_date.isoformat(), "doctor_id": doctor_id},
	)
	assert slots.status_code == 200
	assert slots.json()[0]["doctor_name"] == "Dr Rao"

	unauthorized = client.post(
		"/voice/chat",
		json={"session_id": "private-session", "message": "My name is Asha"},
	)
	assert unauthorized.status_code == 401
	assert client.get("/appointment/mine").status_code == 401


def test_doctor_profile_generates_slots_and_applies_date_blocks(client, monkeypatch):
	monkeypatch.setattr(
		"app.services.appointment_request_service.send_appointment_notification",
		lambda notification, request: None,
	)
	db = client.app.state.test_session_factory()
	doctor_id = add_doctor(db, with_schedule=False)
	doctor = db.get(Doctor, doctor_id)
	doctor.profile_image_url = "https://example.test/doctor.png"
	doctor.consultation_info = "In-person and remote consultations."
	doctor.appointment_duration_minutes = 30
	open_date = date.today() + timedelta(days=14)
	db.add(
		DoctorWeeklyAvailability(
			doctor_id=doctor_id,
			weekday=open_date.weekday(),
			start_time=time(9, 0),
			end_time=time(10, 0),
		)
	)
	db.add(
		DoctorAvailability(
			doctor_id=doctor_id,
			date=open_date,
			start_time=time(9, 30),
			end_time=time(10, 0),
			is_available=False,
		)
	)
	db.commit()
	db.close()

	profile = client.get(f"/doctors/{doctor_id}")
	assert profile.status_code == 200
	assert profile.json()["profile_image_url"] == "https://example.test/doctor.png"
	assert profile.json()["consultation_info"] == "In-person and remote consultations."
	assert profile.json()["appointment_duration_minutes"] == 30
	date_response = client.get(
		f"/doctors/{doctor_id}/available-dates",
		params={"start_date": open_date.isoformat(), "days": 1},
	)
	assert date_response.json()["dates"] == [open_date.isoformat()]
	slots = client.get(
		f"/doctors/{doctor_id}/availability",
		params={"appointment_date": open_date.isoformat()},
	)
	assert [slot["start_time"] for slot in slots.json()] == ["09:00"]
	assert client.get(
		f"/doctors/{doctor_id}/availability",
		params={"appointment_date": (date.today() - timedelta(days=1)).isoformat()},
	).json() == []

	patient = register(client, "Asha", "asha@example.com")
	blocked_request = client.post(
		"/appointment-requests",
		headers=auth_headers(patient),
		json={
			"doctor_id": doctor_id,
			"requested_date": open_date.isoformat(),
			"requested_time": "09:30",
		},
	)
	assert blocked_request.status_code == 409
	available_request = client.post(
		"/appointment-requests",
		headers=auth_headers(patient),
		json={
			"doctor_id": doctor_id,
			"requested_date": open_date.isoformat(),
			"requested_time": "09:00",
		},
	)
	assert available_request.status_code == 201
	assert available_request.json()["status"] == "PENDING"


def test_doctor_availability_management_requires_auth_and_owns_exceptions(client):
	db = client.app.state.test_session_factory()
	doctor_id = add_doctor(db, with_schedule=False)
	db.close()
	path = "/doctors/me/availability/weekly"
	assert client.put(path, json={"appointment_duration_minutes": 30, "windows": []}).status_code == 401

	login = client.post(
		"/auth/doctor/login",
		json={"email": "doctor@example.com", "password": "doctor-secure-password"},
	)
	headers = auth_headers(login.json())
	saved = client.put(
		path,
		headers=headers,
		json={
			"appointment_duration_minutes": 45,
			"windows": [
				{"weekday": 1, "start_time": "09:00", "end_time": "12:00"},
				{"weekday": 1, "start_time": "13:00", "end_time": "17:00"},
			],
		},
	)
	assert saved.status_code == 200
	assert saved.json()["appointment_duration_minutes"] == 45
	assert len(saved.json()["windows"]) == 2
	overlap = client.put(
		path,
		headers=headers,
		json={
			"appointment_duration_minutes": 30,
			"windows": [
				{"weekday": 1, "start_time": "09:00", "end_time": "13:00"},
				{"weekday": 1, "start_time": "12:00", "end_time": "17:00"},
			],
		},
	)
	assert overlap.status_code == 422

	exception = client.post(
		"/doctors/me/availability/exceptions",
		headers=headers,
		json={
			"date": (date.today() + timedelta(days=2)).isoformat(),
			"start_time": "10:00",
			"end_time": "10:30",
			"is_available": False,
		},
	)
	assert exception.status_code == 201
	db = client.app.state.test_session_factory()
	other_id = add_doctor(db, "other@example.com", "Dr Other", with_schedule=False)
	db.close()
	other_login = client.post(
		"/auth/doctor/login",
		json={"email": "other@example.com", "password": "doctor-secure-password"},
	)
	assert client.delete(
		f"/doctors/me/availability/exceptions/{exception.json()['id']}",
		headers=auth_headers(other_login.json()),
	).status_code == 404
	assert other_id != doctor_id


def test_authenticated_voice_transcription_accepts_recorded_audio(client, monkeypatch):
	registered = register(client, "Asha", "asha@example.com")
	monkeypatch.setattr(
		"app.api.voice.transcribe_audio", lambda audio_path: "Book a cardiology visit"
	)

	response = client.post(
		"/voice/transcribe",
		headers=auth_headers(registered),
		files={"audio": ("recording.webm", b"test audio data", "audio/webm")},
	)

	assert response.status_code == 200
	assert response.json() == {"text": "Book a cardiology visit"}


def test_voice_transcription_returns_service_error_instead_of_server_crash(
	client, monkeypatch
):
	registered = register(client, "Asha", "asha@example.com")

	def incompatible_transcription(audio_path):
		raise TypeError("incompatible audio API")

	monkeypatch.setattr("app.api.voice.transcribe_audio", incompatible_transcription)

	response = client.post(
		"/voice/transcribe",
		headers=auth_headers(registered),
		files={"audio": ("recording.webm", b"test audio data", "audio/webm")},
	)

	assert response.status_code == 503
	assert "Speech transcription is unavailable" in response.json()["detail"]


def test_invalid_and_expired_tokens_are_rejected(client):
	registered = register(client, "Asha", "asha@example.com")
	expired_token = jwt.encode(
		{
			"sub": str(registered["patient"]["id"]),
			"role": "patient",
			"exp": datetime.now(timezone.utc) - timedelta(days=1),
		},
		"test-only-signing-secret-at-least-32-chars",
		algorithm="HS256",
	)
	for token in ("not-a-jwt", expired_token):
		response = client.get(
			"/auth/me", headers={"Authorization": f"Bearer {token}"}
		)
		assert response.status_code == 401
	doctor_role_token = create_access_token(registered["patient"]["id"], "doctor")
	role_response = client.get(
		"/auth/me", headers={"Authorization": f"Bearer {doctor_role_token}"}
	)
	assert role_response.status_code == 401


@pytest.mark.parametrize(
	"secret",
	[
		"change-this-in-production",
		"replace-with-a-random-secret-containing-at-least-32-characters",
		"too-short",
	],
)
def test_signing_key_rejects_default_and_short_values(client, monkeypatch, secret):
	monkeypatch.setenv("APP_SECRET_KEY", secret)
	with pytest.raises(RuntimeError, match="random secret"):
		create_access_token(1)


def test_create_tables_adds_doctor_available_days_to_existing_sqlite_schema(monkeypatch):
	engine = create_engine("sqlite://")
	with engine.begin() as connection:
		connection.execute(text(
			"CREATE TABLE doctors ("
			"id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, email VARCHAR, "
			"specialization VARCHAR, hospital VARCHAR, experience INTEGER, "
			"consultation_fee FLOAT)"
		))
	monkeypatch.setattr(database_module, "engine", engine)

	database_module.create_tables()

	columns = {column["name"] for column in inspect(engine).get_columns("doctors")}
	assert "available_days" in columns
	engine.dispose()
