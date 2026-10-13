import os
import smtplib
from email.message import EmailMessage

from ..database.models import AppointmentNotification, AppointmentRequest


def send_appointment_notification(
	notification: AppointmentNotification, request: AppointmentRequest
) -> None:
	host = os.getenv("SMTP_HOST", "").strip()
	username = os.getenv("SMTP_USERNAME", "").strip()
	password = os.getenv("SMTP_PASSWORD", "")
	sender = os.getenv("SMTP_FROM", "").strip()
	if not host or not sender:
		raise RuntimeError("SMTP_HOST and SMTP_FROM must be configured")

	message = EmailMessage()
	message["From"] = sender
	message["To"] = notification.recipient

	if notification.notification_type == "doctor_request":
		message["Subject"] = f"Appointment request #{request.id}"
		message.set_content(
			f"""A patient has requested an appointment.

Request ID: {request.id}
Patient: {request.patient.name}
Patient email: {request.patient.email or 'Not provided'}
Patient phone: {request.patient.phone or 'Not provided'}
Requested date: {request.requested_date.isoformat()}
Requested time: {request.requested_time.strftime('%H:%M')}

Sign in to review and decide this request:
{os.getenv('PUBLIC_FRONTEND_URL', 'http://localhost:5173').rstrip('/')}/doctor
"""
		)
	elif notification.notification_type.startswith("patient_"):
		message["Subject"] = f"Appointment request #{request.id} update"
		frontend_url = os.getenv(
			"PUBLIC_FRONTEND_URL", "http://localhost:5173"
		).rstrip("/")
		if notification.notification_type == "patient_approved":
			content = (
				"Your appointment request was approved and the appointment is confirmed."
			)
		elif notification.notification_type == "patient_rejected":
			content = (
				"Your doctor could not accept this appointment request. "
				"Sign in to review the decision and create another request."
			)
		else:
			content = (
				"The doctor suggested another appointment time. "
				"Sign in to accept or decline the proposal."
			)
		proposal = ""
		if request.status == "COUNTER_PROPOSED":
			proposal = (
				f"\nProposed date: {request.proposed_date.isoformat()}\n"
				f"Proposed time: {request.proposed_time.strftime('%H:%M')}\n"
			)
		message.set_content(
			f"""Hello {request.patient.name},

{content}
Request ID: {request.id}
{proposal}
Review your appointment requests:
{frontend_url}/appointments
"""
		)
	else:
		raise ValueError("Unsupported appointment notification type")

	port = int(os.getenv("SMTP_PORT", "587"))
	with smtplib.SMTP(host, port, timeout=10) as smtp:
		smtp.starttls()
		if username:
			smtp.login(username, password)
		smtp.send_message(message)
