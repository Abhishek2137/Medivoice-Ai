import { useEffect, useState } from "react";
import Conversation from "../components/Conversation";
import DoctorCard from "../components/DoctorCard";
import VoiceButton from "../components/VoiceButton";
import {
	bookAppointment,
	cancelAppointment,
	createAppointmentRequest,
	getDoctorAvailability,
	getMyAppointmentRequests,
	getMyAppointments,
	listDoctors,
	respondToAppointmentProposal,
	retryAppointmentNotifications,
	sendMessage,
} from "../services/api";

function getSessionId() {
	const existing = window.localStorage.getItem("medivoice-session");
	if (existing) return existing;
	const sessionId = `session-${crypto.randomUUID()}`;
	window.localStorage.setItem("medivoice-session", sessionId);
	return sessionId;
}

function speak(text) {
	if ("speechSynthesis" in window) {
		window.speechSynthesis.cancel();
		window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
	}
}

function Understanding({ state }) {
	const fields = [
		["Name", state.patient_name],
		["Doctor", state.specialization],
		["Date", state.date],
		["Time", state.time],
	];

	return (
		<aside className="understanding-card">
			<div className="eyebrow">AI understanding</div>
			<h2>Appointment details</h2>
			<div className="understanding-list">
				{fields.map(([label, value]) => (
					<div className="understanding-row" key={label}>
						<span>{label}</span>
						<strong className={value ? "is-set" : "is-missing"}>{value || "Waiting"}</strong>
					</div>
				))}
			</div>
		</aside>
	);
}

function localDate(offsetDays = 0) {
	const date = new Date();
	date.setDate(date.getDate() + offsetDays);
	return [
		date.getFullYear(),
		String(date.getMonth() + 1).padStart(2, "0"),
		String(date.getDate()).padStart(2, "0"),
	].join("-");
}

function appointmentRequestLabel(status) {
	return {
		PENDING: "Pending Approval",
		APPROVED: "Confirmed",
		REJECTED: "Rejected",
		COUNTER_PROPOSED: "Alternative Proposed",
		CONFIRMED: "Confirmed",
	}[status] || status.replaceAll("_", " ");
}

export function DoctorsDirectory({ onBooked, publicOnly = false, onSignIn }) {
	const [doctors, setDoctors] = useState([]);
	const [slots, setSlots] = useState([]);
	const [date, setDate] = useState(localDate(1));
	const [specialization, setSpecialization] = useState("");
	const [selectedSlot, setSelectedSlot] = useState(null);
	const [isLoading, setIsLoading] = useState(false);
	const [isBooking, setIsBooking] = useState(false);
	const [error, setError] = useState("");

	useEffect(() => {
		let active = true;
		setIsLoading(true);
		setError("");
		Promise.all([
			listDoctors(specialization),
			date ? getDoctorAvailability({ date, specialization }) : Promise.resolve([]),
		])
			.then(([doctorResults, availability]) => {
				if (!active) return;
				setDoctors(doctorResults);
				setSlots(availability);
			})
			.catch((requestError) => {
				if (active) setError(requestError.message);
			})
			.finally(() => {
				if (active) setIsLoading(false);
			});
		return () => { active = false; };
	}, [date, specialization]);

	async function confirmDoctorBooking() {
		if (!selectedSlot) return;
		if (publicOnly) {
			onSignIn?.();
			return;
		}
		setIsBooking(true);
		setError("");
		try {
			const result = await createAppointmentRequest({
				doctorId: selectedSlot.doctor_id,
				date: selectedSlot.date,
				time: selectedSlot.start_time,
				idempotencyKey: crypto.randomUUID(),
			});
			onBooked({
				...result,
				message: "Your appointment request has been sent to the doctor and is awaiting approval.",
				slot: selectedSlot,
			});
			setSelectedSlot(null);
		} catch (requestError) {
			setError(requestError.message);
		} finally {
			setIsBooking(false);
		}
	}

	const specialties = [...new Set(doctors.map((doctor) => doctor.specialization).filter(Boolean))].sort();
	const doctorSlots = (doctorId) => slots.filter((slot) => slot.doctor_id === doctorId);

	return (
		<section className="directory-section">
			<div className="section-heading">
				<div className="eyebrow">Find your care team</div>
				<h2>Doctors</h2>
				<p className="muted-copy">Browse each doctor's profile to see configured dates and request an available time. The doctor reviews requests before confirmation.</p>
			</div>
			<div className="filter-bar">
				<label>Specialization
					<select value={specialization} onChange={(event) => setSpecialization(event.target.value)}>
						<option value="">All specialties</option>
						{specialties.map((item) => <option key={item} value={item}>{item}</option>)}
					</select>
				</label>
				<label>View openings on<input type="date" min={localDate()} value={date} onChange={(event) => setDate(event.target.value)} /></label>
				</div>
				{error && <p className="inline-error" role="alert">{error}</p>}
				{isLoading ? <p className="muted-copy">Loading doctors and time slots...</p> : (
				<div className="directory-grid">
					{doctors.map((doctor) => (
						<article className="directory-card" key={doctor.id}>
							<div className="doctor-avatar" aria-hidden="true">+</div>
							<div className="doctor-details">
								<h3>{doctor.name}</h3>
								<p className="doctor-specialty">{doctor.specialization || "General practice"}</p>
								<p className="doctor-meta">{doctor.hospital || "MediVoice clinic"}</p>
								{doctor.experience != null && <p className="doctor-meta">{doctor.experience} years of experience</p>}
								{doctor.available_days?.length > 0 && <p className="doctor-meta">Available days: {doctor.available_days.join(", ")}</p>}
								{doctor.consultation_fee != null && <p className="doctor-meta">Consultation fee: {doctor.consultation_fee}</p>}
								<a className="text-button profile-link" href={`/doctors/${doctor.id}`}>View profile and all available dates</a>
							</div>
							<div className="directory-slots">
								<strong>Available times</strong>
								{doctorSlots(doctor.id).length ? doctorSlots(doctor.id).map((slot) => (
									<button className="slot-choice" type="button" key={`${slot.date}-${slot.start_time}`} onClick={() => publicOnly ? onSignIn?.() : setSelectedSlot(slot)}>
										{publicOnly ? `Sign in to book · ${slot.start_time}` : `${slot.start_time} – ${slot.end_time}`}
									</button>
								)) : <span className="muted-copy">No openings on this date.</span>}
							</div>
						</article>
					))}
					{doctors.length === 0 && <p className="empty-state">No doctors match that specialty yet.</p>}
				</div>
			)}
			{selectedSlot && (
				<div className="modal-backdrop" role="presentation" onClick={() => setSelectedSlot(null)}>
					<div className="confirmation-modal" role="dialog" aria-modal="true" aria-labelledby="directory-booking-title" onClick={(event) => event.stopPropagation()}>
						<button className="modal-close" type="button" onClick={() => setSelectedSlot(null)} aria-label="Close">×</button>
						<div className="eyebrow">Review appointment</div>
						<h2 id="directory-booking-title">Request this time?</h2>
						<div className="confirmation-details"><strong>{selectedSlot.doctor_name}</strong><span>{selectedSlot.specialization}</span><span>{selectedSlot.hospital}</span><span>{selectedSlot.date} at {selectedSlot.start_time}</span></div>
						{error && <p className="inline-error" role="alert">{error}</p>}
						<div className="modal-actions"><button className="secondary-button" type="button" onClick={() => setSelectedSlot(null)}>Go back</button><button className="primary-button" type="button" onClick={confirmDoctorBooking} disabled={isBooking}>{isBooking ? "Sending..." : "Request appointment"}</button></div>
					</div>
				</div>
			)}
		</section>
	);
}

function AppointmentsPage({ patient }) {
	const [appointments, setAppointments] = useState([]);
	const [requests, setRequests] = useState([]);
	const [doctors, setDoctors] = useState([]);
	const [filters, setFilters] = useState({ date: "", doctorId: "", status: "" });
	const [isLoading, setIsLoading] = useState(false);
	const [workingId, setWorkingId] = useState(null);
	const [error, setError] = useState("");

	async function refreshAppointments() {
		setIsLoading(true);
		setError("");
		try {
			const [rows, requestRows, doctorRows] = await Promise.all([
				getMyAppointments(filters),
				getMyAppointmentRequests(),
				listDoctors(),
			]);
			setAppointments(rows);
			setRequests(requestRows);
			setDoctors(doctorRows);
		} catch (requestError) {
			setError(requestError.message);
		} finally {
			setIsLoading(false);
		}
	}

	useEffect(() => { refreshAppointments(); }, [filters.date, filters.doctorId, filters.status]);

	async function cancel(id) {
		if (!window.confirm("Cancel this appointment?")) return;
		setError("");
		try {
			await cancelAppointment(id);
			await refreshAppointments();
		} catch (requestError) {
			setError(requestError.message);
		}
	}

	async function respond(requestId, decision) {
		setWorkingId(requestId);
		setError("");
		try {
			await respondToAppointmentProposal(requestId, decision);
			await refreshAppointments();
		} catch (requestError) {
			setError(requestError.message);
		} finally {
			setWorkingId(null);
		}
	}

	async function retryNotification(requestId) {
		setWorkingId(requestId);
		setError("");
		try {
			await retryAppointmentNotifications(requestId);
			await refreshAppointments();
		} catch (requestError) {
			setError(requestError.message);
		} finally {
			setWorkingId(null);
		}
	}

	const doctorNames = Object.fromEntries(doctors.map((doctor) => [doctor.id, doctor.name]));

	return (
		<section className="appointments-section">
			<div className="section-heading"><div className="eyebrow">Your care schedule</div><h2>Appointments</h2><p className="muted-copy">Appointments shown here are private to {patient.name}.</p></div>
			<h3>Appointment requests</h3>
			{isLoading ? <p className="muted-copy">Loading your requests...</p> : requests.length ? (
				<div className="appointment-list request-history">
					{requests.map((request) => (
						<article className="appointment-row request-history-row" key={request.id}>
							<div className="appointment-primary">
								<span className="appointment-id">Request #{request.id}</span>
								<strong>{request.doctor_name}</strong>
								<span>Preferred: {request.requested_date} at {request.requested_time}</span>
								{request.proposed_date && <span>Doctor suggested: {request.proposed_date} at {request.proposed_time}</span>}
								{request.decision_details && <span className="decision-details">{request.decision_details}</span>}
								{request.rejection_reason && <span>Reason: {request.rejection_reason}</span>}
								{request.notification_status.includes("FAILED") && <span className="inline-error">An email could not be delivered.</span>}
							</div>
							<span className={`status-pill status-${request.status.toLowerCase().replaceAll("_", "-")}`}>{appointmentRequestLabel(request.status)}</span>
							<div className="appointment-actions">
								{request.status === "COUNTER_PROPOSED" && <>
									<button className="primary-button" type="button" disabled={workingId != null} onClick={() => respond(request.id, "accept")}>{workingId === request.id ? "Saving..." : "Accept proposal"}</button>
									<button className="danger-button" type="button" disabled={workingId != null} onClick={() => respond(request.id, "decline")}>Decline</button>
								</>}
								{request.notification_status.includes("FAILED") && <button className="secondary-button" type="button" disabled={workingId != null} onClick={() => retryNotification(request.id)}>Retry email</button>}
							</div>
						</article>
					))}
				</div>
			) : <p className="empty-state">You have no appointment requests yet.</p>}
			<h3 className="confirmed-appointments-heading">Confirmed appointments</h3>
			<div className="filter-bar">
				<label>Date<input type="date" value={filters.date} onChange={(event) => setFilters({ ...filters, date: event.target.value })} /></label>
				<label>Doctor<select value={filters.doctorId} onChange={(event) => setFilters({ ...filters, doctorId: event.target.value })}><option value="">All doctors</option>{doctors.map((doctor) => <option key={doctor.id} value={doctor.id}>{doctor.name}</option>)}</select></label>
				<label>Status<select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}><option value="">All statuses</option><option value="pending_doctor_confirmation">Awaiting confirmation</option><option value="confirmed">Confirmed</option><option value="cancelled">Cancelled</option><option value="completed">Completed</option><option value="rejected">Rejected</option></select></label>
			</div>
			{error && <p className="inline-error" role="alert">{error}</p>}
			{isLoading ? <p className="muted-copy">Loading your appointments...</p> : appointments.length ? (
				<div className="appointment-list">
					{appointments.map((appointment) => (
						<article className="appointment-row" key={appointment.id}>
							<div className="appointment-primary"><span className="appointment-id">Appointment #{appointment.id}</span><strong>{doctorNames[appointment.doctor_id] || `Doctor #${appointment.doctor_id}`}</strong><span>{patient.name} · {appointment.appointment_date} at {appointment.appointment_time}</span></div>
							<span className={`status-pill status-${(appointment.status || "pending").replaceAll("_", "-")}`}>{(appointment.status || "pending").replaceAll("_", " ")}</span>
							{appointment.status === "confirmed" && <div className="appointment-actions"><button className="danger-button" type="button" onClick={() => cancel(appointment.id)}>Cancel</button></div>}
						</article>
					))}
				</div>
			) : <p className="empty-state">No appointments match these filters. Browse doctors to book a time.</p>}
		</section>
	);
}

export default function PatientHome({ patient, onLogout }) {
	const [activeTab, setActiveTab] = useState(
		() => window.location.pathname === "/appointments"
			? "appointments"
			: new URLSearchParams(window.location.search).get("tab") === "doctors"
				? "doctors"
				: "home",
	);
	const [sessionId] = useState(getSessionId);
	const [messages, setMessages] = useState([
		{ id: "welcome", role: "assistant", text: "Hello. How can I help you today?" },
	]);
	const [state, setState] = useState({});
	const [input, setInput] = useState("");
	const [slots, setSlots] = useState([]);
	const [selectedSlot, setSelectedSlot] = useState(null);
	const [isSending, setIsSending] = useState(false);
	const [error, setError] = useState("");
	const [booking, setBooking] = useState(null);

	async function submitMessage(message) {
		const cleanMessage = message.trim();
		if (!cleanMessage || isSending) return;

		setInput("");
		setError("");
		setMessages((current) => [
			...current,
			{ id: `${Date.now()}-user`, role: "user", text: cleanMessage },
		]);
		setIsSending(true);

		try {
			const response = await sendMessage(sessionId, cleanMessage);
			setState(response.state || {});
			setSlots(response.availability || []);
			setMessages((current) => [
				...current,
				{ id: `${Date.now()}-assistant`, role: "assistant", text: response.message },
			]);
			speak(response.message);
		} catch (requestError) {
			setError(requestError.message);
		} finally {
			setIsSending(false);
		}
	}

	async function confirmBooking() {
		if (!selectedSlot) return;
		setIsSending(true);
		setError("");
		try {
			const response = await bookAppointment(
				sessionId,
				selectedSlot.doctor_id,
				selectedSlot.start_time,
			);
			setBooking({ ...response, slot: selectedSlot });
			setSelectedSlot(null);
			setSlots([]);
			speak(response.message);
		} catch (requestError) {
			setError(requestError.message);
		} finally {
			setIsSending(false);
		}
	}

	function handleBooked(result) {
		setBooking(result);
		setActiveTab("appointments");
		speak(result.message);
	}

	const tabs = [
		["home", "Home"],
		["appointments", "Appointments"],
		["doctors", "Doctors"],
	];

	return (
		<div className="app-shell">
			<header className="topbar">
				<a className="brand" href="/" aria-label="MediVoice home">
					<span className="brand-mark">+</span>
					<span>MediVoice <em>AI</em></span>
				</a>
				<div className="topbar-actions"><span className="online-dot" /> Online <span className="account-name">{patient.name}</span><button className="logout-button" type="button" onClick={onLogout}>Sign out</button></div>
			</header>

			<main className="page-content">
				{activeTab === "home" && <section className="hero-copy">
					<div className="eyebrow">Your calm path to care</div>
					<h1>Book care in<br /><span>your own words.</span></h1>
					<p>Tell us what you need by voice or text, or request any future date and preferred time. Your doctor reviews each request before it is confirmed.</p>
				</section>}

				{activeTab === "home" && <div className="workspace-grid">
					<section className="conversation-column">
						<div className="conversation-header"><span>Appointment assistant</span><span className="secure-label">Private session</span></div>
						<Conversation messages={messages} />
						{isSending && <div className="thinking"><span /> Finding the best next step</div>}

						<VoiceButton sessionId={sessionId} onTranscript={(transcript) => submitMessage(transcript)} disabled={isSending} />
						<div className="transcript-hint">Speak naturally. Your words will appear here before they are sent.</div>
						<form className="message-form" onSubmit={(event) => { event.preventDefault(); submitMessage(input); }}>
							<input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Or type your message..." aria-label="Message" disabled={isSending} />
							<button type="submit" disabled={isSending || !input.trim()} aria-label="Send message">Send</button>
						</form>
						{error && <p className="inline-error page-error">{error}</p>}
					</section>

					<div className="side-column">
						<Understanding state={state} />
						{slots.length > 0 && (
							<section className="slots-section">
								<div className="section-heading"><div className="eyebrow">Matches for you</div><h2>Available appointments</h2></div>
								<div className="slot-list">{slots.map((slot) => <DoctorCard key={`${slot.doctor_id}-${slot.start_time}`} slot={slot} onSelect={setSelectedSlot} />)}</div>
							</section>
						)}
					</div>
				</div>}
				{activeTab === "appointments" && <AppointmentsPage patient={patient} />}
				{activeTab === "doctors" && <DoctorsDirectory onBooked={handleBooked} />}
			</main>

			<footer className="bottom-nav">{tabs.map(([tab, label]) => <button className={activeTab === tab ? "active" : ""} type="button" key={tab} onClick={() => { setActiveTab(tab); window.history.replaceState({}, "", tab === "appointments" ? "/appointments" : "/"); }} aria-current={activeTab === tab ? "page" : undefined}>{label}</button>)}</footer>

			{selectedSlot && (
				<div className="modal-backdrop" role="presentation" onClick={() => setSelectedSlot(null)}>
					<div className="confirmation-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title" onClick={(event) => event.stopPropagation()}>
						<button className="modal-close" type="button" onClick={() => setSelectedSlot(null)} aria-label="Close">x</button>
						<div className="success-mark">+</div>
						<div className="eyebrow">Review appointment</div>
						<h2 id="confirm-title">Ready to book?</h2>
						<p className="modal-intro">This submits a request for the doctor to review. Nothing is confirmed until the doctor approves.</p>
						<div className="confirmation-details"><strong>{selectedSlot.doctor_name}</strong><span>{selectedSlot.specialization}</span><span>{selectedSlot.hospital}</span><span>{state.date} at {selectedSlot.start_time}</span></div>
						<div className="modal-actions"><button className="secondary-button" type="button" onClick={() => setSelectedSlot(null)}>Go back</button><button className="primary-button" type="button" onClick={confirmBooking} disabled={isSending}>Send request</button></div>
					</div>
				</div>
			)}

			{booking && (
				<div className="modal-backdrop" role="presentation">
					<div className="confirmation-modal success-modal" role="dialog" aria-modal="true" aria-labelledby="success-title">
						<div className="success-mark">!</div><div className="eyebrow">Request sent</div><h2 id="success-title">Waiting for doctor approval</h2>
						<p className="modal-intro">{booking.message}</p><div className="confirmation-details"><strong>{booking.doctor_name || booking.slot?.doctor_name || `Doctor #${booking.doctor_id}`}</strong><span>{booking.requested_date || booking.appointment_date} at {booking.requested_time || booking.appointment_time}</span><span>Request #{booking.id || booking.request_id}</span></div>
						<button className="primary-button full-width" type="button" onClick={() => setBooking(null)}>Done</button>
					</div>
				</div>
			)}
		</div>
	);
}
