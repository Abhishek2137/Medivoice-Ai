export default function Conversation({ messages }) {
	return (
		<section className="conversation-panel" aria-label="Conversation">
			{messages.map((message) => (
				<div className={`message-row ${message.role}`} key={message.id}>
					{message.role === "assistant" && <span className="message-mark">M</span>}
					<div className="message-bubble">{message.text}</div>
				</div>
			))}
		</section>
	);
}
