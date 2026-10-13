from .embeddings import embed_texts
from .vectorstore import get_collection


def search_knowledge(query: str, limit: int = 5) -> list[dict]:
	query = query.strip()
	if not query:
		return []

	collection = get_collection()
	if collection.count() == 0:
		return []

	result = collection.query(
		query_embeddings=embed_texts([query]),
		n_results=max(1, min(limit, 20)),
		include=["documents", "metadatas", "distances"],
	)
	return [
		{
			"text": text,
			"source": metadata.get("source", "unknown"),
			"distance": distance,
		}
		for text, metadata, distance in zip(
			result.get("documents", [[]])[0],
			result.get("metadatas", [[]])[0],
			result.get("distances", [[]])[0],
		)
	]
