
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker

from .models import Base


project_root = Path(__file__).resolve().parents[3]
load_dotenv(project_root / ".env")
load_dotenv(project_root / "backend" / ".env")


def get_database_url() -> str:
	# Prefer an explicit DATABASE_URL value when configured.
	configured_url = os.environ.get("DATABASE_URL")
	if configured_url:
		return configured_url

	# Support default Postgres-style configuration in deployment environments.
	user = os.environ.get("DB_USER")
	password = os.environ.get("DB_PASSWORD")
	host = os.environ.get("DB_HOST", "localhost")
	port = os.environ.get("DB_PORT", "5432")
	db_name = os.environ.get("DB_NAME", "voice_rag")
	if user and password:
		return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"

	# Local development fallback
	return "sqlite:///./test.db"


engine = create_engine(get_database_url(), echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()


def create_tables():
	Base.metadata.create_all(bind=engine)
	if engine.dialect.name == "postgresql":
		with engine.begin() as connection:
			connection.execute(text(
				"ALTER TABLE doctors ADD COLUMN IF NOT EXISTS email VARCHAR"
			))
			connection.execute(text(
				"ALTER TABLE doctors ADD COLUMN IF NOT EXISTS available_days VARCHAR"
			))
	elif engine.dialect.name == "sqlite":
		doctor_columns = {
			column["name"] for column in inspect(engine).get_columns("doctors")
		}
		if "available_days" not in doctor_columns:
			with engine.begin() as connection:
				connection.execute(
					text("ALTER TABLE doctors ADD COLUMN available_days VARCHAR")
				)
