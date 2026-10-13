import tempfile
from datetime import date, time
from pathlib import Path
from typing import Dict, Any

from fastapi import (
	APIRouter,
	BackgroundTasks,
	Depends,
	File,
	HTTPException,
	Query,
	UploadFile,
)
from av.error import FFmpegError
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from ..ai.speech import transcribe_audio
from ..database.database import get_db
from ..database.models import Patient
from ..services.auth_service import get_current_patient
from ..services.appointment_request_service import (
	create_appointment_request,
)
from ..services.conversation_service import (
	get_conversation_manager,
	reset_conversation,
)
from .appointment_requests import _schedule_pending_notifications

router = APIRouter(prefix="/voice", tags=["voice"])

ALLOWED_AUDIO_TYPES = {
	"audio/webm",
	"audio/wav",
	"audio/x-wav",
	"audio/mpeg",
	"audio/mp4",
}


class ChatRequest(BaseModel):
	"""Request model for conversation endpoint."""
	session_id: str = Field(min_length=1)
	message: str


class ChatResponse(BaseModel):
	"""Response model for conversation endpoint."""
	status: str
	message: str
	state: Dict[str, Any]
	missing_field: str | None = None
	availability: list[Dict[str, Any]] = Field(default_factory=list)


class BookVoiceRequest(BaseModel):
	session_id: str = Field(min_length=1)
	doctor_id: int
	appointment_time: str


class BookVoiceResponse(BaseModel):
	status: str
	message: str
	request_id: int
	appointment_id: int | None = None
	doctor_id: int
	appointment_date: str
	appointment_time: str


@router.post("/transcribe")
async def transcribe_voice(
	audio: UploadFile = File(...),
	patient: Patient = Depends(get_current_patient),
):
	content_type = (audio.content_type or "").split(";", 1)[0].strip().lower()
	if content_type not in ALLOWED_AUDIO_TYPES:
		raise HTTPException(status_code=415, detail="Unsupported audio format")

	file_suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
	try:
		with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as temporary_file:
			temporary_file.write(await audio.read())
			temporary_path = Path(temporary_file.name)

		try:
			text = await run_in_threadpool(transcribe_audio, temporary_path)
		finally:
			temporary_path.unlink(missing_ok=True)
	except RuntimeError as error:
		raise HTTPException(status_code=503, detail=str(error)) from error
	except FFmpegError as error:
		raise HTTPException(
			status_code=422,
			detail="The recording could not be decoded. Please record again and try.",
		) from error
	except TypeError as error:
		raise HTTPException(
			status_code=503,
			detail="Speech transcription is unavailable due to a server compatibility issue.",
		) from error

	return {"text": text}


@router.post("/chat", response_model=ChatResponse)
async def chat(
	request: ChatRequest,
	db=Depends(get_db),
	patient: Patient = Depends(get_current_patient),
) -> ChatResponse:
	"""
	Process user message through conversation manager.
	
	Extracts appointment information and decides what to ask next.
	"""
	try:
		manager = get_conversation_manager(f"{patient.id}:{request.session_id}")
		if not manager.state.get("patient_name"):
			manager.state["patient_name"] = patient.name
		result = manager.process(request.message)
		availability = []
		if result["status"] == "ready_for_availability":
			requested_time = time.fromisoformat(result["state"]["time"])
			rows = search_availability_by_specialization(
				db,
				date.fromisoformat(result["state"]["date"]),
				result["state"]["specialization"],
				requested_time,
			)
			requested_doctor = result["state"].get("doctor_name")
			if requested_doctor:
				rows = [
					(row, doctor)
					for row, doctor in rows
					if requested_doctor.lower() in doctor.name.lower()
				]
			availability = [
				{
					"doctor_id": doctor.id,
					"doctor_name": doctor.name,
					"specialization": doctor.specialization,
					"hospital": doctor.hospital,
					"start_time": slot.start_time.isoformat(),
					"end_time": slot.end_time.isoformat(),
				}
				for slot, doctor in rows
			]
			if availability:
				suggestions = "; ".join(
					f"{slot['doctor_name']} at {slot['start_time']}"
					for slot in availability[:5]
				)
				result["message"] = (
					f"I found {len(availability)} available slot(s): {suggestions}. "
					"Which doctor and time would you like to book?"
				)
			else:
				result["message"] = (
					"I could not find an available slot for that date and specialization."
				)
		
		return ChatResponse(
			status=result["status"],
			message=result["message"],
			state=result["state"],
			missing_field=result.get("missing_field"),
			availability=availability,
		)
	except HTTPException:
		raise
	except (TypeError, ValueError) as error:
		raise HTTPException(status_code=422, detail="Invalid appointment details") from error
	except Exception as error:
		raise HTTPException(status_code=500, detail=str(error)) from error


@router.post("/book", response_model=BookVoiceResponse, status_code=201)
async def book_voice_appointment(
	request: BookVoiceRequest,
	background_tasks: BackgroundTasks,
	db=Depends(get_db),
	patient: Patient = Depends(get_current_patient),
) -> BookVoiceResponse:
	session_key = f"{patient.id}:{request.session_id}"
	manager = get_conversation_manager(session_key)
	state = manager.get_state()
	if not manager.is_complete():
		raise HTTPException(status_code=400, detail="Complete the conversation first")

	try:
		appointment_date = date.fromisoformat(state["date"])
		appointment_time = time.fromisoformat(request.appointment_time)
	except ValueError as error:
		raise HTTPException(status_code=422, detail="Invalid appointment date or time") from error

	appointment_request = create_appointment_request(
		db,
		patient,
		request.doctor_id,
		appointment_date,
		appointment_time,
		", ".join(state.get("symptoms", [])) or None,
	)
	_schedule_pending_notifications(background_tasks, db, appointment_request.id)
	reset_conversation(session_key)
	return BookVoiceResponse(
		status=appointment_request.status,
		message="Your appointment request has been sent to the doctor and is awaiting approval.",
		request_id=appointment_request.id,
		doctor_id=appointment_request.doctor_id,
		appointment_date=appointment_request.requested_date.isoformat(),
		appointment_time=appointment_request.requested_time.isoformat(),
	)


@router.post("/reset")
async def reset_chat(
	session_id: str = Query(min_length=1),
	patient: Patient = Depends(get_current_patient),
) -> Dict[str, str]:
	"""Reset conversation state for a new user."""
	reset_conversation(f"{patient.id}:{session_id}")
	return {"status": "reset", "message": "Conversation reset successfully"}


@router.get("/state")
async def get_chat_state(
	session_id: str = Query(min_length=1),
	patient: Patient = Depends(get_current_patient),
) -> Dict[str, Any]:
	"""Get current conversation state."""
	manager = get_conversation_manager(f"{patient.id}:{session_id}")
	return {
		"state": manager.get_state(),
		"is_complete": manager.is_complete(),
		"missing_field": manager.get_missing_field(),
	}
