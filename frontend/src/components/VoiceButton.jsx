import { useRef, useState } from "react";
import { Mic } from "lucide-react";
import { transcribeAudio } from "../services/api";

export default function VoiceButton({ sessionId, onTranscript, disabled = false }) {
	const recorderRef = useRef(null);
	const streamRef = useRef(null);
	const [isListening, setIsListening] = useState(false);
	const [isTranscribing, setIsTranscribing] = useState(false);
	const [error, setError] = useState("");

	async function toggleRecording() {
		if (isListening) {
			recorderRef.current?.stop();
			return;
		}

		if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
			setError("Voice recording is not supported in this browser.");
			return;
		}

		try {
			setError("");
			const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
			const recorder = new MediaRecorder(stream);
			const chunks = [];
			streamRef.current = stream;
			recorderRef.current = recorder;

			recorder.ondataavailable = (event) => chunks.push(event.data);
			recorder.onstop = async () => {
				stream.getTracks().forEach((track) => track.stop());
				setIsListening(false);
					setIsTranscribing(true);
				try {
					const result = await transcribeAudio(
						sessionId,
						new Blob(chunks, { type: recorder.mimeType || "audio/webm" }),
					);
					if (result.text?.trim()) onTranscript(result.text.trim());
				} catch (transcriptionError) {
					setError(transcriptionError.message);
					} finally {
						setIsTranscribing(false);
				}
			};

			recorder.start();
			setIsListening(true);
		} catch (recordingError) {
			setError(recordingError.message || "Microphone access was not granted.");
		}
	}

	return (
		<div className="voice-control">
			<button
				className={`voice-button ${isListening ? "is-listening" : ""}`}
				type="button"
				onClick={toggleRecording}
				 disabled={disabled || isTranscribing}
				 aria-label={isListening ? "Stop recording" : "Start recording"}
			>
				<span className="voice-icon" aria-hidden="true">
					{isListening ? "■" : <Mic size={24} strokeWidth={2.2} />}
				</span>
				<span>{isListening ? "Tap to stop" : isTranscribing ? "Transcribing..." : "Tap to speak"}</span>
				<span className="voice-wave" aria-hidden="true"><i /><i /><i /><i /><i /></span>
			</button>
			{error && <p className="inline-error">{error}</p>}
		</div>
	);
}
