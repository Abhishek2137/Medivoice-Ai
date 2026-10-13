export default function DoctorCard({ slot, onSelect }) {
	const time = new Date(`1970-01-01T${slot.start_time}`).toLocaleTimeString([], {
		hour: "numeric",
		minute: "2-digit",
	});

	return (
		<article className="doctor-card">
			<div className="doctor-avatar" aria-hidden="true">+</div>
			<div className="doctor-details">
				<h3>{slot.doctor_name}</h3>
				<p className="doctor-specialty">{slot.specialization}</p>
				<p className="doctor-meta">{slot.hospital || "MediVoice clinic"}</p>
				<div className="slot-time"><span>Available</span><strong>{time}</strong></div>
			</div>
			<button className="select-button" type="button" onClick={() => onSelect(slot)}>
				Select slot
			</button>
		</article>
	);
}
