from functools import lru_cache

from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
	return SentenceTransformer("all-MiniLM-L6-v2")


def embed_texts(texts: list[str]) -> list[list[float]]:
	if not texts:
		return []
	return get_embedding_model().encode(
		texts, normalize_embeddings=True, show_progress_bar=False
	).tolist()
