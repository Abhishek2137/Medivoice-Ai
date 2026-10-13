import json
from pathlib import Path
from typing import Any

from .embeddings import embed_texts
from .vectorstore import get_collection


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"


def _flatten(value: Any, prefix: str = "") -> list[str]:
	if isinstance(value, dict):
		parts = []
		for key, child in value.items():
			parts.extend(_flatten(child, f"{prefix}{key}: "))
		return parts
	if isinstance(value, list):
		return [item for child in value for item in _flatten(child, prefix)]
	return [f"{prefix}{value}"] if value not in (None, "") else []


def load_documents(data_dir: Path = DATA_DIR) -> list[dict[str, Any]]:
	documents = []
	for source_path in sorted(data_dir.glob("*.json")):
		try:
			content = json.loads(source_path.read_text(encoding="utf-8"))
		except (OSError, json.JSONDecodeError):
			continue

		items = content if isinstance(content, list) else [content]
		for index, item in enumerate(items):
			if not isinstance(item, dict):
				continue
			text = ". ".join(_flatten(item))
			if text:
				documents.append({
					"id": f"{source_path.stem}-{index}",
					"text": text,
					"metadata": {"source": source_path.name, "type": source_path.stem},
				})
	return documents


def ingest_documents(data_dir: Path = DATA_DIR) -> int:
	documents = load_documents(data_dir)
	if not documents:
		return 0

	collection = get_collection()
	texts = [document["text"] for document in documents]
	collection.upsert(
		ids=[document["id"] for document in documents],
		documents=texts,
		metadatas=[document["metadata"] for document in documents],
		embeddings=embed_texts(texts),
	)
	return len(documents)
