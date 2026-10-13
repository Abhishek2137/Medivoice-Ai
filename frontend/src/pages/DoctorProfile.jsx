import { useEffect, useRef, useState } from "react";
import {
	createAppointmentRequest,
	getDoctorAvailableDates,
	getDoctorDaySlots,
	getDoctorProfile,
} from "../services/api";

function localDate() {
	const today = new Date();
	return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
}

export default function DoctorProfile({ doctorId, patient }) {
	const [doctor, setDoctor] = useState(null);
	const [dates, setDates] = useState([]);
	const [selectedDate, setSelectedDate] = useState("");
	const [slots, setSlots] = useState([]);
	const [selectedTime, setSelectedTime] = useState("");
	const [reason, setReason] = useState("");
	const [isLoading, setIsLoading] = useState(true);
	const [isLoadingSlots, setIsLoadingSlots] = useState(false);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [error, setError] = useState("");
	const [success, setSuccess] = useState("");
	const idempotencyKey = useRef(null);

	useEffect(() => {
		let active = true;
		setIsLoading(true);
		Promise.all([
			getDoctorProfile(doctorId),
			getDoctorAvailableDates(doctorId, localDate()),
		]).then(([profile, availability]) => {
			if (!active) return;
			setDoctor(profile);
			setDates(availability.dates);
			setSelectedDate(availability.dates[0] || "");
		}).catch((requestError) => {
			if (active) setError(requestError.message);
		}).finally(() => {
			if (active) setIsLoading(false);
		});
		return () => { active = false; };
	}, [doctorId]);

	useEffect(() => {
		if (!selectedDate) {
			setSlots([]);
			setSelectedTime("");
			return undefined;
		}
		let active = true;
		setIsLoadingSlots(true);
		setSelectedTime("");
		getDoctorDaySlots(doctorId, selectedDate).then((results) => {
			if (active) setSlots(results);
		}).catch((requestError) => {
			if (active) setError(requestError.message);
		}).finally(() => {
			if (active) setIsLoadingSlots(false);
		});
		return () => { active = false; };
	}, [doctorId, selectedDate]);

	async function submitRequest(event) {
		event.preventDefault();
		if (!patient || !selectedDate || !selectedTime || isSubmitting) return;
		setIsSubmitting(true);
		setError("");
		setSuccess("");
		idempotencyKey.current ||= crypto.randomUUID();
		try {
			await createAppointmentRequest({
				doctorId: Number(doctorId),
				date: selectedDate,
				time: selectedTime,
				reason,
				idempotencyKey: idempotencyKey.current,
			});
			idempotencyKey.current = null;
			setSuccess("Your appointment request has been sent to the doctor and is awaiting approval.");
			setReason("");
			setSelectedTime("");
		} catch (requestError) {
			setError(requestError.message);
		} finally {
			setIsSubmitting(false);
		}
	}

	return (
		<div className="app-shell">
			<header className="topbar">
				<a className="brand" href="/"><span className="brand-mark">+</span><span>MediVoice <em>AI</em></span></a>
				<div className="topbar-actions"><a className="text-button" href="/?tab=doctors">Back to doctors</a>{patient && <a className="text-button" href="/appointments">Appointment history</a>}</div>
			</header>
			<main className="page-content doctor-profile-page">
				{isLoading ? <p className="muted-copy">Loading doctor profile...</p> : doctor ? <>
					{error && <p className="inline-error" role="alert">{error}</p>}
					{success && <p className="success-message" role="status">{success}</p>}
					<section className="doctor-profile-card">
						{doctor.profile_image_url
							? <img className="doctor-profile-image" src={doctor.profile_image_url} alt={doctor.name} />
							: <div className="doctor-profile-image doctor-avatar" aria-hidden="true">+</div>}
						<div>
							<div className="eyebrow">Doctor profile</div>
							<h1>{doctor.name}</h1>
							<p className="doctor-specialty">{doctor.specialization || "General practice"}</p>
							<p className="doctor-meta">{doctor.hospital || "MediVoice clinic"}{doctor.experience != null ? ` · ${doctor.experience} years of experience` : ""}</p>
							{doctor.consultation_fee != null && <p className="doctor-meta">Consultation fee: {doctor.consultation_fee}</p>}
							{doctor.consultation_info && <p className="consultation-info">{doctor.consultation_info}</p>}
							<p className="doctor-meta">Consultation duration: {doctor.appointment_duration_minutes} minutes</p>
						</div>
					</section>

					<section className="profile-booking-card">
						<div className="section-heading"><div className="eyebrow">Schedule</div><h2>Available appointment times</h2></div>
						{dates.length ? (
							<form onSubmit={submitRequest}>
								<label>Available date
									<select required value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)}>
										{dates.map((availableDate) => <option key={availableDate} value={availableDate}>{availableDate}</option>)}
									</select>
								</label>
								{isLoadingSlots ? <p className="muted-copy">Loading available times...</p> : slots.length ? (
									<div className="profile-slot-grid" role="group" aria-label="Available time slots">
										{slots.map((slot) => (
											<button
												className={`profile-slot${selectedTime === slot.start_time ? " selected" : ""}`}
												key={slot.start_time}
												type="button"
												aria-pressed={selectedTime === slot.start_time}
												onClick={() => setSelectedTime(slot.start_time)}
											>{slot.start_time} – {slot.end_time}<span>Available</span></button>
										))}
									</div>
								) : <p className="empty-state">No openings remain on this date. Select another available date.</p>}
								<label>Reason for visit (optional)
									<textarea value={reason} onChange={(event) => setReason(event.target.value)} maxLength={2000} rows={3} />
								</label>
								{patient ? (
									<button className="primary-button" type="submit" disabled={!selectedTime || isSubmitting || isLoadingSlots}>
										{isSubmitting ? "Sending request..." : "Request selected time"}
									</button>
								) : <a className="primary-button profile-sign-in" href="/">Sign in to request this appointment</a>}
								<p className="request-availability-note">Your appointment remains pending until the doctor approves it.</p>
							</form>
						) : <p className="empty-state">This doctor has not configured any upcoming appointment availability yet. Please check back later.</p>}
					</section>
				</> : !error && <p className="empty-state">Doctor not found.</p>}
			</main>
		</div>
	);
}
