from pathlib import Path

import chromadb


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHROMA_PATH = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "medical_knowledge"


def get_collection():
	client = chromadb.PersistentClient(path=str(CHROMA_PATH))
	return client.get_or_create_collection(
		name=COLLECTION_NAME,
		metadata={"hnsw:space": "cosine"},
	)
