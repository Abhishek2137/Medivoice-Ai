from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..rag.ingest import ingest_documents
from ..rag.retriever import search_knowledge


router = APIRouter(prefix="/rag", tags=["rag"])


class RagSearchRequest(BaseModel):
	query: str = Field(min_length=1)
	limit: int = Field(default=5, ge=1, le=20)


@router.post("/ingest")
def ingest_rag():
	try:
		count = ingest_documents()
		return {"status": "ingested", "documents": count}
	except Exception as error:
		raise HTTPException(status_code=500, detail="RAG ingestion failed") from error


@router.post("/search")
def search_rag(request: RagSearchRequest):
	try:
		return {"query": request.query, "results": search_knowledge(request.query, request.limit)}
	except Exception as error:
		raise HTTPException(status_code=500, detail="RAG search failed") from error