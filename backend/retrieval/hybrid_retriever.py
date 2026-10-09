import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from backend.models import ChunkProvenance
from backend.config import settings
from backend.retrieval.bm25_index import BM25KeywordIndex
from backend.retrieval.vector_store import ChromaVectorStore

class RetrievedPassage(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    page: int
    section: str
    heading: str
    combined_score: float
    vector_score: float
    bm25_score: float
    match_type: str  # HYBRID, VECTOR_ONLY, BM25_ONLY

class HybridRetriever:
    """
    Hybrid Retriever combining Dense Semantic Embeddings (ChromaDB)
    and Sparse BM25 Keyword Search with Reciprocal Rank Fusion (RRF).
    """

    def __init__(self, vector_store: Optional[ChromaVectorStore] = None):
        self.vector_store = vector_store or ChromaVectorStore()
        self.bm25_indices: Dict[str, BM25KeywordIndex] = {}

    def index_document(self, document_id: str, chunks: List[ChunkProvenance]):
        # 1. Store in Chroma Vector DB
        self.vector_store.add_chunks(document_id, chunks)

        # 2. Build BM25 Index for exact identifiers, standards, and clauses
        bm25_idx = BM25KeywordIndex()
        bm25_idx.build_index(chunks)
        self.bm25_indices[document_id] = bm25_idx

    def get_or_create_bm25(self, document_id: str, chunks: Optional[List[ChunkProvenance]] = None) -> Optional[BM25KeywordIndex]:
        if document_id in self.bm25_indices:
            return self.bm25_indices[document_id]
        if chunks:
            bm25_idx = BM25KeywordIndex()
            bm25_idx.build_index(chunks)
            self.bm25_indices[document_id] = bm25_idx
            return bm25_idx
        return None

    def search(
        self,
        document_id: str,
        query: str,
        top_k: int = settings.TOP_K_RETRIEVAL,
        alpha: float = settings.HYBRID_ALPHA,
        chunks_fallback: Optional[List[ChunkProvenance]] = None
    ) -> List[RetrievedPassage]:
        """
        Executes hybrid search across vector and BM25 channels,
        performing rank fusion and score weighting.
        """
        clean_query = self._preprocess_query(query)

        # 1. Semantic Vector Search
        vector_results = self.vector_store.search(document_id, clean_query, top_k=top_k * 2)

        # 2. BM25 Search
        bm25_idx = self.get_or_create_bm25(document_id, chunks_fallback)
        bm25_results = bm25_idx.search(clean_query, top_k=top_k * 2) if bm25_idx else []

        # 3. Fuse scores
        merged_candidates: Dict[str, Dict[str, Any]] = {}

        # Process Vector candidates
        for rank, (chunk, v_score) in enumerate(vector_results, start=1):
            merged_candidates[chunk.chunk_id] = {
                "chunk": chunk,
                "vector_score": v_score,
                "bm25_score": 0.0,
                "vector_rank": rank,
                "bm25_rank": None
            }

        # Process BM25 candidates
        for rank, (chunk, b_score) in enumerate(bm25_results, start=1):
            cid = chunk.chunk_id
            if cid in merged_candidates:
                merged_candidates[cid]["bm25_score"] = b_score
                merged_candidates[cid]["bm25_rank"] = rank
            else:
                merged_candidates[cid] = {
                    "chunk": chunk,
                    "vector_score": 0.0,
                    "bm25_score": b_score,
                    "vector_rank": None,
                    "bm25_rank": rank
                }

        # If both empty and we have chunks_fallback, do a simple substring scan
        if not merged_candidates and chunks_fallback:
            for c in chunks_fallback[:top_k]:
                merged_candidates[c.chunk_id] = {
                    "chunk": c,
                    "vector_score": 0.5,
                    "bm25_score": 0.5,
                    "vector_rank": 1,
                    "bm25_rank": 1
                }

        # Compute RRF & weighted hybrid score
        scored_passages: List[RetrievedPassage] = []
        k_rrf = 60.0

        for cid, item in merged_candidates.items():
            chunk: ChunkProvenance = item["chunk"]
            v_score = item["vector_score"]
            b_score = item["bm25_score"]
            v_rank = item["vector_rank"]
            b_rank = item["bm25_rank"]

            # RRF contribution
            rrf_v = (1.0 / (k_rrf + v_rank)) if v_rank is not None else 0.0
            rrf_b = (1.0 / (k_rrf + b_rank)) if b_rank is not None else 0.0
            rrf_combined = rrf_v + rrf_b

            # Weighted linear score
            linear_score = (alpha * v_score) + ((1.0 - alpha) * b_score)
            
            # Final normalized combined score
            combined_score = (linear_score * 0.7) + (min(rrf_combined * 30.0, 1.0) * 0.3)

            match_type = "HYBRID"
            if v_score > 0 and b_score == 0:
                match_type = "VECTOR_ONLY"
            elif b_score > 0 and v_score == 0:
                match_type = "BM25_ONLY"

            scored_passages.append(
                RetrievedPassage(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    text=chunk.text,
                    page=chunk.page,
                    section=chunk.section,
                    heading=chunk.heading or "",
                    combined_score=round(combined_score, 4),
                    vector_score=round(v_score, 4),
                    bm25_score=round(b_score, 4),
                    match_type=match_type
                )
            )

        scored_passages.sort(key=lambda x: x.combined_score, reverse=True)
        return scored_passages[:top_k]

    @staticmethod
    def _preprocess_query(query: str) -> str:
        # Normalize common tender terms
        q = query.strip()
        # Expand common acronyms for better retrieval
        q = re.sub(r'\bEMD\b', 'EMD Earnest Money Deposit', q, flags=re.I)
        q = re.sub(r'\bPBG\b', 'PBG Performance Bank Guarantee', q, flags=re.I)
        q = re.sub(r'\bSLA\b', 'SLA Service Level Agreement', q, flags=re.I)
        return q
