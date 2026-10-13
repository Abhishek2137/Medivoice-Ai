import os
from pathlib import Path


_model = None


def transcribe_audio(audio_path: str | Path) -> str:
	global _model

	try:
		from faster_whisper import WhisperModel
	except ImportError as error:
		raise RuntimeError(
			"Speech transcription is not configured. Install faster-whisper first."
		) from error

	if _model is None:
		_model = WhisperModel(
			os.getenv("WHISPER_MODEL", "base"),
			device=os.getenv("WHISPER_DEVICE", "cpu"),
			compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
		)

	segments, _ = _model.transcribe(
		str(audio_path),
		language=os.getenv("WHISPER_LANGUAGE", "en"),
		initial_prompt=(
			"Healthcare appointment booking. Doctors, dermatology, cardiology, "
			"dermatologist, rash, symptoms, appointment, hospital."
		),
		vad_filter=True,
	)
	return " ".join(segment.text.strip() for segment in segments).strip()
