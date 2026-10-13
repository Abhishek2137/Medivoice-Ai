from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..database.models import Doctor, DoctorCredential, Patient, PatientCredential
from ..services.auth_service import (
	create_access_token,
	get_current_doctor,
	get_current_patient,
	hash_password,
	verify_password,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


class RegisterRequest(BaseModel):
	name: str = Field(min_length=1, max_length=120)
	email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)
	password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
	email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)
	password: str = Field(min_length=1, max_length=128)


class PatientSummary(BaseModel):
	id: int
	name: str
	email: str
	role: str = "patient"


class AuthResponse(BaseModel):
	access_token: str
	token_type: str = "bearer"
	patient: PatientSummary


class DoctorLoginRequest(BaseModel):
	email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)
	password: str = Field(min_length=1, max_length=128)


class DoctorSummary(BaseModel):
	id: int
	name: str
	email: str
	role: str = "doctor"


class DoctorAuthResponse(BaseModel):
	access_token: str
	token_type: str = "bearer"
	doctor: DoctorSummary


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
	email = request.email.strip().lower()
	name = request.name.strip()
	if not name:
		raise HTTPException(status_code=422, detail="Name cannot be blank")
	if db.query(PatientCredential).filter_by(email=email).first() is not None:
		raise HTTPException(status_code=409, detail="An account with this email already exists")

	try:
		patient = Patient(name=name, email=email)
		db.add(patient)
		db.flush()
		credential = PatientCredential(
			patient_id=patient.id,
			email=email,
			password_hash=hash_password(request.password),
			role="patient",
		)
		db.add(credential)
		db.commit()
	except IntegrityError as error:
		db.rollback()
		raise HTTPException(
			status_code=409, detail="An account with this email already exists"
		) from error
	db.refresh(patient)
	token = create_access_token(patient.id, credential.role)
	return AuthResponse(
		access_token=token,
		patient=PatientSummary(id=patient.id, name=patient.name, email=email),
	)


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
	email = request.email.strip().lower()
	credential = db.query(PatientCredential).filter_by(email=email).first()
	if credential is None or not verify_password(request.password, credential.password_hash):
		raise HTTPException(status_code=401, detail="Invalid email or password")
	patient = db.get(Patient, credential.patient_id)
	if patient is None:
		raise HTTPException(status_code=401, detail="Invalid email or password")

	return AuthResponse(
		access_token=create_access_token(patient.id, credential.role),
		patient=PatientSummary(
			id=patient.id,
			name=patient.name,
			email=credential.email,
			role=credential.role,
		),
	)


@router.get("/me", response_model=PatientSummary)
def current_account(patient=Depends(get_current_patient)) -> PatientSummary:
	credential = patient.credential
	return PatientSummary(
		id=patient.id,
		name=patient.name,
		email=credential.email,
		role=credential.role,
	)


@router.post("/doctor/login", response_model=DoctorAuthResponse)
def doctor_login(
	request: DoctorLoginRequest, db: Session = Depends(get_db)
) -> DoctorAuthResponse:
	email = request.email.strip().lower()
	credential = db.query(DoctorCredential).filter_by(email=email).first()
	if credential is None or not verify_password(
		request.password, credential.password_hash
	):
		raise HTTPException(status_code=401, detail="Invalid email or password")
	doctor = db.get(Doctor, credential.doctor_id)
	if doctor is None:
		raise HTTPException(status_code=401, detail="Doctor account is unavailable")
	return DoctorAuthResponse(
		access_token=create_access_token(doctor.id, "doctor"),
		doctor=DoctorSummary(
			id=doctor.id,
			name=doctor.name,
			email=credential.email,
		),
	)


@router.get("/doctor/me", response_model=DoctorSummary)
def current_doctor(
	doctor: Doctor = Depends(get_current_doctor),
	db: Session = Depends(get_db),
) -> DoctorSummary:
	credential = db.get(DoctorCredential, doctor.id)
	if credential is None:
		raise HTTPException(status_code=401, detail="Doctor account is unavailable")
	return DoctorSummary(
		id=doctor.id,
		name=doctor.name,
		email=credential.email,
	)
