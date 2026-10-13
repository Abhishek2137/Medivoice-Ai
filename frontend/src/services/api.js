const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
	const headers = new Headers(options.headers || {});
	const tokenKey = window.location.pathname.startsWith("/doctor")
		? "medivoice-doctor-token"
		: "medivoice-token";
	const token = window.sessionStorage.getItem(tokenKey);
	if (token) headers.set("Authorization", `Bearer ${token}`);
	if (options.body && !(options.body instanceof FormData)) {
		headers.set("Content-Type", "application/json");
	}

	const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
	if (!response.ok) {
		const error = await response.json().catch(() => ({}));
		throw new Error(error.detail || "The request could not be completed.");
	}
	if (response.status === 204) return null;
	return response.json();
}

export function registerPatient(details) {
	return request("/auth/register", {
		method: "POST",
		body: JSON.stringify(details),
	});
}

export function loginPatient(credentials) {
	return request("/auth/login", {
		method: "POST",
		body: JSON.stringify(credentials),
	});
}

export function getCurrentPatient() {
	return request("/auth/me");
}

export function loginDoctor(credentials) {
	return request("/auth/doctor/login", {
		method: "POST",
		body: JSON.stringify(credentials),
	});
}

export function getCurrentDoctor() {
	return request("/auth/doctor/me");
}

export function listDoctors(specialization = "") {
	const query = specialization ? `?specialization=${encodeURIComponent(specialization)}` : "";
	return request(`/doctors${query}`);
}

export function getDoctorProfile(doctorId) {
	return request(`/doctors/${doctorId}`);
}

export function getDoctorAvailableDates(doctorId, startDate) {
	const params = new URLSearchParams({ days: "90" });
	if (startDate) params.set("start_date", startDate);
	return request(`/doctors/${doctorId}/available-dates?${params}`);
}

export function getDoctorDaySlots(doctorId, date) {
	return request(`/doctors/${doctorId}/availability?appointment_date=${encodeURIComponent(date)}`);
}

export function getDoctorWeeklyAvailability() {
	return request("/doctors/me/availability/weekly");
}

export function saveDoctorWeeklyAvailability(schedule) {
	return request("/doctors/me/availability/weekly", {
		method: "PUT",
		body: JSON.stringify(schedule),
	});
}

export function getDoctorAvailabilityExceptions() {
	return request("/doctors/me/availability/exceptions");
}

export function addDoctorAvailabilityException(exception) {
	return request("/doctors/me/availability/exceptions", {
		method: "POST",
		body: JSON.stringify(exception),
	});
}

export function deleteDoctorAvailabilityException(exceptionId) {
	return request(`/doctors/me/availability/exceptions/${exceptionId}`, { method: "DELETE" });
}

export function getDoctorAvailability({ date, doctorId, specialization } = {}) {
	const params = new URLSearchParams();
	if (date) params.set("appointment_date", date);
	if (doctorId) params.set("doctor_id", doctorId);
	if (specialization) params.set("specialization", specialization);
	return request(`/doctors/availability?${params}`);
}

export function getMyAppointments(filters = {}) {
	const params = new URLSearchParams();
	if (filters.date) params.set("appointment_date", filters.date);
	if (filters.doctorId) params.set("doctor_id", filters.doctorId);
	if (filters.status) params.set("status", filters.status);
	const query = params.size ? `?${params}` : "";
	return request(`/appointment/mine${query}`);
}

export function createAppointment({ doctorId, date, time, symptoms }) {
	return request("/appointment/book", {
		method: "POST",
		body: JSON.stringify({
			doctor_id: doctorId,
			appointment_date: date,
			appointment_time: time,
			symptoms: symptoms || null,
		}),
	});
}

export function createAppointmentRequest({ doctorId, date, time, reason, idempotencyKey }) {
	return request("/appointment-requests", {
		method: "POST",
		headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {},
		body: JSON.stringify({
			doctor_id: doctorId,
			requested_date: date,
			requested_time: time,
			reason: reason || null,
		}),
	});
}

export function getMyAppointmentRequests() {
	return request("/appointment-requests/mine");
}

export function getDoctorAppointmentRequests(pendingOnly = true) {
	return request(`/appointment-requests/doctor/mine?pending_only=${pendingOnly}`);
}

export function approveAppointmentRequest(requestId) {
	return request(`/appointment-requests/${requestId}/approve`, { method: "POST" });
}

export function rejectAppointmentRequest(requestId, reason) {
	return request(`/appointment-requests/${requestId}/reject`, {
		method: "POST",
		body: JSON.stringify({ reason }),
	});
}

export function proposeAppointmentTime(requestId, date, time) {
	return request(`/appointment-requests/${requestId}/counter-propose`, {
		method: "POST",
		body: JSON.stringify({ proposed_date: date, proposed_time: time }),
	});
}

export function respondToAppointmentProposal(requestId, decision) {
	return request(`/appointment-requests/${requestId}/proposal-response`, {
		method: "POST",
		body: JSON.stringify({ decision }),
	});
}

export function retryAppointmentNotifications(requestId, doctor = false) {
	const suffix = doctor ? "doctor-notifications" : "notifications";
	return request(`/appointment-requests/${requestId}/${suffix}/retry`, {
		method: "POST",
	});
}

export function cancelAppointment(appointmentId) {
	return request(`/appointment/${appointmentId}`, { method: "DELETE" });
}

export function rescheduleAppointment(appointmentId, date, time) {
	return request(`/appointment/${appointmentId}/reschedule`, {
		method: "PUT",
		body: JSON.stringify({ appointment_date: date, appointment_time: time }),
	});
}

export function sendMessage(sessionId, message) {
	return request("/voice/chat", {
		method: "POST",
		body: JSON.stringify({ session_id: sessionId, message }),
	});
}

export async function transcribeAudio(sessionId, audioBlob) {
	const formData = new FormData();
	formData.append("audio", audioBlob, "recording.webm");
	const result = await request("/voice/transcribe", {
		method: "POST",
		body: formData,
	});
	return { ...result, sessionId };
}

export function bookAppointment(sessionId, doctorId, appointmentTime) {
	return request("/voice/book", {
		method: "POST",
		body: JSON.stringify({
			session_id: sessionId,
			doctor_id: doctorId,
			appointment_time: appointmentTime,
		}),
	});
}
