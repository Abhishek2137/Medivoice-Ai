import { useEffect, useState } from "react";
import {
	addDoctorAvailabilityException,
	approveAppointmentRequest,
	deleteDoctorAvailabilityException,
	getDoctorAvailabilityExceptions,
	getDoctorAppointmentRequests,
	getDoctorWeeklyAvailability,
	proposeAppointmentTime,
	rejectAppointmentRequest,
	retryAppointmentNotifications,
	saveDoctorWeeklyAvailability,
} from "../services/api";

const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function futureDate() {
	const value = new Date();
	value.setDate(value.getDate() + 1);
	return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

export default function DoctorDashboard({ doctor, onLogout }) {
	const [requests, setRequests] = useState([]);
	const [isLoading, setIsLoading] = useState(true);
	const [workingId, setWorkingId] = useState(null);
	const [notice, setNotice] = useState("");
	const [error, setError] = useState("");
	const [schedule, setSchedule] = useState({ appointment_duration_minutes: 30, windows: [] });
	const [exceptions, setExceptions] = useState([]);
	const [exceptionKind, setExceptionKind] = useState("available");
	const [availabilityLoading, setAvailabilityLoading] = useState(true);
	const [availabilitySaving, setAvailabilitySaving] = useState(false);

	async function refresh() {
		setError("");
		try {
			setRequests(await getDoctorAppointmentRequests());
		} catch (requestError) {
			setError(requestError.message);
		} finally {
			setIsLoading(false);
		}
	}

	useEffect(() => { refresh(); }, []);

	async function refreshAvailability() {
		setAvailabilityLoading(true);
		try {
			const [weekly, dateExceptions] = await Promise.all([
				getDoctorWeeklyAvailability(),
				getDoctorAvailabilityExceptions(),
			]);
			setSchedule(weekly);
			setExceptions(dateExceptions);
		} catch (requestError) {
			setError(requestError.message);
		} finally {
			setAvailabilityLoading(false);
		}
	}

	useEffect(() => { refreshAvailability(); }, []);

	function updateWindow(index, field, value) {
		setSchedule((current) => ({
			...current,
			windows: current.windows.map((window, rowIndex) => rowIndex === index
				? { ...window, [field]: field === "weekday" ? Number(value) : value }
				: window),
		}));
	}

	async function saveSchedule(event) {
		event.preventDefault();
		setAvailabilitySaving(true);
		setError("");
		try {
			setSchedule(await saveDoctorWeeklyAvailability(schedule));
			setNotice("Weekly availability was saved.");
		} catch (requestError) {
			setError(requestError.message);
		} finally {
			setAvailabilitySaving(false);
		}
	}

	async function addException(event) {
		event.preventDefault();
		const formElement = event.currentTarget;
		const form = new FormData(formElement);
		const exceptionType = form.get("exception-type");
		setAvailabilitySaving(true);
		setError("");
		try {
			const result = await addDoctorAvailabilityException({
				date: form.get("exception-date"),
				start_time: exceptionType === "unavailable" ? "00:00" : form.get("exception-start"),
				end_time: exceptionType === "unavailable" ? "23:59" : form.get("exception-end"),
				is_available: exceptionType === "available",
			});
			setExceptions((current) => [...current, result].sort((a, b) => `${a.date}${a.start_time}`.localeCompare(`${b.date}${b.start_time}`)));
			formElement.reset();
			setExceptionKind("available");
			setNotice("Date-specific availability was saved.");
		} catch (requestError) {
			setError(requestError.message);
		} finally {
			setAvailabilitySaving(false);
		}
	}

	async function removeException(exceptionId) {
		setAvailabilitySaving(true);
		setError("");
		try {
			await deleteDoctorAvailabilityException(exceptionId);
			setExceptions((current) => current.filter((exception) => exception.id !== exceptionId));
		} catch (requestError) {
			setError(requestError.message);
		} finally {
			setAvailabilitySaving(false);
		}
	}

	async function decide(requestId, action) {
		setWorkingId(requestId);
		setError("");
		setNotice("");
		try {
			await action();
			setNotice(`Request #${requestId} has been updated.`);
			await refresh();
		} catch (requestError) {
			setError(requestError.message);
		} finally {
			setWorkingId(null);
		}
	}

	async function reject(event, requestId) {
		event.preventDefault();
		const reason = new FormData(event.currentTarget).get("rejection-reason");
		await decide(requestId, () => rejectAppointmentRequest(requestId, reason));
	}

	async function propose(event, requestId) {
		event.preventDefault();
		const values = new FormData(event.currentTarget);
		await decide(requestId, () => proposeAppointmentTime(
			requestId,
			values.get("proposed-date"),
			values.get("proposed-time"),
		));
	}

	return (
		<div className="app-shell">
			<header className="topbar">
				<a className="brand" href="/doctor"><span className="brand-mark">+</span><span>MediVoice <em>AI</em></span></a>
				<div className="topbar-actions"><span className="online-dot" /> Doctor portal <span className="account-name">{doctor.name}</span><button className="logout-button" type="button" onClick={onLogout}>Sign out</button></div>
			</header>
			<main className="page-content doctor-dashboard">
				<div className="section-heading"><div className="eyebrow">Secure doctor workspace</div><h2>Appointment requests</h2><p className="muted-copy">Review requests assigned to your account. Approval confirms the appointment only after the slot is checked again.</p></div>
				{notice && <p className="success-message" role="status">{notice}</p>}
				{error && <p className="inline-error" role="alert">{error}</p>}
				<section className="availability-management">
					<div className="section-heading"><div className="eyebrow">Doctor schedule</div><h2>Manage availability</h2><p className="muted-copy">Weekly hours repeat automatically. Date-specific openings override weekly hours for that date; blocked periods are removed from bookable slots.</p></div>
					{availabilityLoading ? <p className="muted-copy">Loading schedule...</p> : <>
						<form className="weekly-schedule-form" onSubmit={saveSchedule}>
							<label>Appointment duration (minutes)
								<input type="number" min="5" max="240" step="5" value={schedule.appointment_duration_minutes} onChange={(event) => setSchedule((current) => ({ ...current, appointment_duration_minutes: Number(event.target.value) }))} required />
							</label>
							{schedule.windows.map((window, index) => (
								<div className="schedule-window" key={`${window.weekday}-${window.start_time}-${index}`}>
									<label>Weekday<select value={window.weekday} onChange={(event) => updateWindow(index, "weekday", event.target.value)}>{weekdays.map((day, weekday) => <option value={weekday} key={day}>{day}</option>)}</select></label>
									<label>Start<input type="time" value={window.start_time} onChange={(event) => updateWindow(index, "start_time", event.target.value)} required /></label>
									<label>End<input type="time" value={window.end_time} onChange={(event) => updateWindow(index, "end_time", event.target.value)} required /></label>
									<button className="danger-button" type="button" onClick={() => setSchedule((current) => ({ ...current, windows: current.windows.filter((_, rowIndex) => rowIndex !== index) }))}>Remove</button>
								</div>
							))}
							{!schedule.windows.length && <p className="empty-state">No weekly hours are configured. Only date-specific available slots can be requested.</p>}
							<div className="schedule-actions">
								<button className="secondary-button" type="button" onClick={() => setSchedule((current) => ({ ...current, windows: [...current.windows, { weekday: 0, start_time: "", end_time: "" }] }))}>Add working-hours window</button>
								<button className="primary-button" type="submit" disabled={availabilitySaving}>{availabilitySaving ? "Saving..." : "Save weekly schedule"}</button>
							</div>
						</form>
						<form className="date-exception-form" onSubmit={addException}>
							<h3>Date-specific opening, break, or unavailable period</h3>
							<label>Date<input name="exception-date" type="date" min={futureDate()} required /></label>
							<label>Start<input name="exception-start" type="time" required={exceptionKind !== "unavailable"} disabled={exceptionKind === "unavailable"} /></label>
							<label>End<input name="exception-end" type="time" required={exceptionKind !== "unavailable"} disabled={exceptionKind === "unavailable"} /></label>
							<label>Type<select name="exception-type" value={exceptionKind} onChange={(event) => setExceptionKind(event.target.value)}><option value="available">Available hours (override weekly)</option><option value="blocked">Break / unavailable period</option><option value="unavailable">Unavailable all day</option></select></label>
							<button className="secondary-button" type="submit" disabled={availabilitySaving}>Add date exception</button>
						</form>
						{exceptions.length > 0 && <ul className="availability-exception-list">{exceptions.map((exception) => (
							<li key={exception.id}><span>{exception.date} · {exception.start_time}–{exception.end_time} · {exception.is_available ? "Available" : "Blocked"}</span><button className="danger-button" type="button" disabled={availabilitySaving} onClick={() => removeException(exception.id)}>Remove</button></li>
						))}</ul>}
					</>}
				</section>
				{isLoading ? <p className="muted-copy">Loading your requests...</p> : requests.length ? (
					<div className="appointment-list">
						{requests.map((request) => (
							<article className="doctor-request-card" key={request.id}>
								<div className="appointment-primary">
									<span className="appointment-id">Request #{request.id}</span>
									<strong>{request.patient_name}</strong>
									<span>{request.patient_email || "No email"} · {request.patient_phone || "No phone"}</span>
									<span>Preferred: {request.requested_date} at {request.requested_time}</span>
									{request.reason && <p className="request-reason"><strong>Reason:</strong> {request.reason}</p>}
								</div>
								<div className="doctor-request-actions">
									<button className="primary-button" type="button" disabled={workingId != null} onClick={() => decide(request.id, () => approveAppointmentRequest(request.id))}>
										{workingId === request.id ? "Saving..." : "Approve"}
									</button>
									{request.notification_status.includes("FAILED") && <button className="secondary-button" type="button" disabled={workingId != null} onClick={() => decide(request.id, () => retryAppointmentNotifications(request.id, true))}>Retry email notification</button>}
									<form className="decision-form" onSubmit={(event) => reject(event, request.id)}>
										<label>Reason for rejection<input name="rejection-reason" required minLength={3} maxLength={1000} /></label>
										<button className="danger-button" type="submit" disabled={workingId != null}>Reject</button>
									</form>
									<form className="decision-form" onSubmit={(event) => propose(event, request.id)}>
										<label>Suggest another date<input name="proposed-date" type="date" min={futureDate()} required /></label>
										<label>Time<input name="proposed-time" type="time" required /></label>
										<button className="secondary-button" type="submit" disabled={workingId != null}>Suggest alternative</button>
									</form>
								</div>
							</article>
						))}
					</div>
				) : <p className="empty-state">There are no pending appointment requests.</p>}
			</main>
		</div>
	);
}