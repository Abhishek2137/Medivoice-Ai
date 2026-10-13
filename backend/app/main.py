import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.appointments import router as appointment_router
from .api.appointment_requests import router as appointment_request_router
from .api.auth import router as auth_router
from .api.conversation import router as conversation_router
from .api.doctors import router as doctors_router
from .api.voice import router as voice_router
from .api.rag import router as rag_router
from .database.database import create_tables
from .services.auth_service import _secret_key


def _get_cors_origins() -> list[str]:
	configured = os.getenv(
		"CORS_ORIGINS",
		"http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
	)
	return [origin.strip() for origin in configured.split(",") if origin.strip()]


app = FastAPI(title="Voice RAG Appointment API")
app.add_middleware(
	CORSMiddleware,
	allow_origins=_get_cors_origins(),
	allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):(517[0-9]|417[0-9])+$",
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)
app.include_router(appointment_router)
app.include_router(appointment_request_router)
app.include_router(auth_router)
app.include_router(conversation_router)
app.include_router(doctors_router)
app.include_router(voice_router)
app.include_router(rag_router)


@app.on_event("startup")
def on_startup():
	_secret_key()
	create_tables()


@app.get("/")
def read_root():
	return {"status": "ok", "app": os.getenv("APP_NAME", "voice-rag-appointment")}


@app.get("/health")
def health_check():
	return {"status": "ok", "service": "backend"}


@app.get("/healthz")
def health_check_z():
	return {"status": "ok"}
