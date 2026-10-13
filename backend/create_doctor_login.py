import argparse
import getpass
import sys
from pathlib import Path

from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database.database import SessionLocal
from app.database.models import Doctor, DoctorCredential
from app.services.auth_service import hash_password


def main() -> int:
	parser = argparse.ArgumentParser(
		description="Create a doctor login for an existing registered doctor."
	)
	parser.add_argument("--doctor-id", type=int, required=True)
	parser.add_argument("--email", required=True)
	args = parser.parse_args()
	email = args.email.strip().lower()
	password = getpass.getpass("New doctor password (10+ characters): ")
	if len(password) < 10:
		parser.error("Doctor passwords must contain at least 10 characters")

	with SessionLocal() as db:
		doctor = db.get(Doctor, args.doctor_id)
		if doctor is None:
			parser.error("No doctor exists with that ID")
		if not doctor.email or doctor.email.strip().lower() != email:
			parser.error("The email must match the registered doctor email")
		if db.get(DoctorCredential, doctor.id) is not None:
			parser.error("This doctor already has a login")
		db.add(
			DoctorCredential(
				doctor_id=doctor.id,
				email=email,
				password_hash=hash_password(password),
			)
		)
		try:
			db.commit()
		except IntegrityError:
			db.rollback()
			parser.error("That email is already registered to another doctor login")
	print(f"Doctor login created for {email}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
