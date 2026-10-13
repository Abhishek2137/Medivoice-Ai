from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field


class AppointmentSearchRequest(BaseModel):
	doctor_id: int | None = None
	appointment_date: date


class AppointmentBookRequest(BaseModel):
	patient_id: int | None = None
	doctor_id: int
	appointment_date: date
	appointment_time: time
	symptoms: str | None = Field(default=None, max_length=2000)


class AppointmentResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	patient_id: int
	doctor_id: int
	appointment_date: date
	appointment_time: time
	status: str | None
	symptoms: str | None


class DoctorResponse(BaseModel):
	model_config = ConfigDict(from_attributes=True)

	id: int
	name: str
	specialization: str | None
	hospital: str | None
	experience: int | None
	consultation_fee: float | None
