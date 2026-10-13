from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..database.models import Patient
from ..services.appointment_service import find_available_doctors
from ..services.conversation_service import get_conversation_manager
from ..services.auth_service import get_current_patient

router = APIRouter(prefix="/conversation", tags=["conversation"])

class ConversationMessageRequest(BaseModel):
	session_id: str = Field(min_length=1)
	message: str = Field(min_length=1)


class ConversationMessageResponse(BaseModel):
	status: str
	message: str
	data: dict
	availability: list[dict] = Field(default_factory=list)


@router.post("/message", response_model=ConversationMessageResponse)
def conversation_message(
	request: ConversationMessageRequest,
	db: Session = Depends(get_db),
	patient: Patient = Depends(get_current_patient),
) -> ConversationMessageResponse:
	manager = get_conversation_manager(f"{patient.id}:{request.session_id}")
	result = manager.process(request.message)
	availability = []

	if result["status"] == "ready_for_availability":
		try:
			availability_result = find_available_doctors(
				db,
				specialization=result["state"]["specialization"],
				date=result["state"]["date"],
				preferred_time=result["state"]["time"],
			)
		except ValueError as error:
			raise HTTPException(
				status_code=422,
				detail="The appointment date or time could not be understood",
			) from error

		availability = [
			{
				"doctor_id": doctor["id"],
				"doctor_name": doctor["name"],
				"specialization": doctor["specialization"],
				"time": doctor["time"],
			}
			for doctor in availability_result["doctors"]
		]
		result["message"] = (
			f"I found {len(availability)} available appointment slot(s)."
			if availability
			else "I could not find an available slot for that request."
		)
		result["status"] = "availability_found" if availability else "no_availability"

	return ConversationMessageResponse(
		status=result["status"],
		message=result["message"],
		data=result["state"],
		availability=availability,
	)