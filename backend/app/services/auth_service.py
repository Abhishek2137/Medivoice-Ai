import os
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..database.models import (
	Doctor,
	DoctorCredential,
	Patient,
	PatientCredential,
)

ALGORITHM = "HS256"
TOKEN_LIFETIME = timedelta(hours=12)
bearer_scheme = HTTPBearer(auto_error=False)


def _secret_key() -> str:
	secret = os.getenv("APP_SECRET_KEY", "")
	if (
		len(secret) < 32
		or secret == "change-this-in-production"
		or secret.startswith("replace-with-a-random-secret")
	):
		raise RuntimeError(
			"Set APP_SECRET_KEY to a random secret containing at least 32 characters."
		)
	return secret


def hash_password(password: str) -> str:
	password_bytes = hashlib.sha256(
		b"bcrypt-sha256\x00" + password.encode("utf-8")
	).digest()
	return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
	try:
		password_bytes = hashlib.sha256(
			b"bcrypt-sha256\x00" + password.encode("utf-8")
		).digest()
		return bcrypt.checkpw(password_bytes, password_hash.encode("ascii"))
	except (ValueError, TypeError):
		return False


def create_access_token(patient_id: int, role: str = "patient") -> str:
	now = datetime.now(timezone.utc)
	payload = {
		"sub": str(patient_id),
		"role": role,
		"iat": now,
		"exp": now + TOKEN_LIFETIME,
	}
	return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def get_current_patient(
	credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
	db: Session = Depends(get_db),
) -> Patient:
	if credentials is None or credentials.scheme.lower() != "bearer":
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Authentication required",
			headers={"WWW-Authenticate": "Bearer"},
		)
	try:
		payload = jwt.decode(credentials.credentials, _secret_key(), algorithms=[ALGORITHM])
		patient_id = int(payload["sub"])
		if payload.get("role") != "patient":
			raise ValueError("Invalid role")
	except (jwt.InvalidTokenError, KeyError, TypeError, ValueError, RuntimeError) as error:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid or expired access token",
			headers={"WWW-Authenticate": "Bearer"},
		) from error

	patient = db.get(Patient, patient_id)
	credential = db.get(PatientCredential, patient_id)
	if patient is None or credential is None or credential.role != "patient":
		raise HTTPException(status_code=401, detail="Patient account is unavailable")
	return patient


def get_current_doctor(
	credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
	db: Session = Depends(get_db),
) -> Doctor:
	if credentials is None or credentials.scheme.lower() != "bearer":
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Authentication required",
			headers={"WWW-Authenticate": "Bearer"},
		)
	try:
		payload = jwt.decode(credentials.credentials, _secret_key(), algorithms=[ALGORITHM])
		doctor_id = int(payload["sub"])
		if payload.get("role") != "doctor":
			raise ValueError("Invalid role")
	except (jwt.InvalidTokenError, KeyError, TypeError, ValueError, RuntimeError) as error:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid or expired access token",
			headers={"WWW-Authenticate": "Bearer"},
		) from error

	doctor = db.get(Doctor, doctor_id)
	credential = db.get(DoctorCredential, doctor_id)
	if doctor is None or credential is None:
		raise HTTPException(status_code=401, detail="Doctor account is unavailable")
	return doctor
