import json
from typing import List, Dict, Any, Tuple
import chromadb
from chromadb.config import Settings as ChromaSettings
from backend.config import settings
from backend.models import ChunkProvenance

class ChromaVectorStore:
    """
    ChromaDB-based vector store for semantic retrieval of tender chunks.
    Preserves page provenance, metadata, and computes normalized similarity scores.
    """

    def __init__(self, persist_dir: str | None = None):
        self.persist_dir = persist_dir or str(settings.CHROMA_PERSIST_DIR)
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection_name = "tender_chunks_collection"
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, document_id: str, chunks: List[ChunkProvenance]):
        if not chunks:
            return

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "document_id": document_id,
                "page": c.page,
                "section": c.section,
                "heading": c.heading or "General",
                "char_count": len(c.text)
            }
            for c in chunks
        ]

        # Chroma upsert in batches of 100
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            end_idx = min(i + batch_size, len(ids))
            self.collection.upsert(
                ids=ids[i:end_idx],
                documents=documents[i:end_idx],
                metadatas=metadatas[i:end_idx]
            )

    def search(self, document_id: str, query: str, top_k: int = 5) -> List[Tuple[ChunkProvenance, float]]:
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where={"document_id": document_id}
            )

            scored_chunks: List[Tuple[ChunkProvenance, float]] = []
            if not results or not results["ids"] or not results["ids"][0]:
                return []

            ids = results["ids"][0]
            docs = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0] if results.get("distances") else [0.0] * len(ids)

            for i in range(len(ids)):
                cid = ids[i]
                doc_text = docs[i]
                meta = metadatas[i] or {}
                dist = distances[i]
                # Cosine distance: similarity = max(0.0, 1.0 - distance)
                sim_score = max(0.0, min(1.0, 1.0 - float(dist)))

                chunk = ChunkProvenance(
                    chunk_id=cid,
                    document_id=meta.get("document_id", document_id),
                    text=doc_text,
                    page=int(meta.get("page", 1)),
                    section=str(meta.get("section", "General")),
                    heading=str(meta.get("heading", "")),
                    metadata=meta
                )
                scored_chunks.append((chunk, sim_score))

            return scored_chunks

        except Exception as e:
            # Fallback for empty collection or error
            return []

    def delete_document_chunks(self, document_id: str):
        try:
            self.collection.delete(where={"document_id": document_id})
        except Exception:
            pass
