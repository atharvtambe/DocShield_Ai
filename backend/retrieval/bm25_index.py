import re
from typing import List, Dict, Any, Tuple
from rank_bm25 import BM25Okapi
from backend.models import ChunkProvenance

class BM25KeywordIndex:
    """
    BM25 Keyword Index designed for procurement and tender documents.
    Preserves exact acronyms, numbers, standards (e.g. ISO 9001, IS 456), currencies, and clauses.
    """

    def __init__(self):
        self.chunk_ids: List[str] = []
        self.chunks_map: Dict[str, ChunkProvenance] = {}
        self.bm25: BM25Okapi | None = None
        self.corpus_size = 0

    @staticmethod
    def tokenize(text: str) -> List[str]:
        # Lowercase, but preserve hyphens/colons in identifiers like ISO-9001 or IS:456
        clean_text = text.lower()
        # Find alphanumeric tokens plus hyphenated standards
        tokens = re.findall(r'[a-z0-9]+(?:[\-\:\.\/][a-z0-9]+)*', clean_text)
        return tokens

    def build_index(self, chunks: List[ChunkProvenance]):
        self.chunk_ids = []
        self.chunks_map = {}
        tokenized_corpus: List[List[str]] = []

        for chunk in chunks:
            self.chunk_ids.append(chunk.chunk_id)
            self.chunks_map[chunk.chunk_id] = chunk
            # Tokenize combining heading + text + section
            full_context = f"{chunk.section} {chunk.heading} {chunk.text}"
            tokenized_corpus.append(self.tokenize(full_context))

        self.corpus_size = len(chunks)
        if tokenized_corpus:
            self.bm25 = BM25Okapi(tokenized_corpus)
        else:
            self.bm25 = None

    def search(self, query: str, top_k: int = 5) -> List[Tuple[ChunkProvenance, float]]:
        if not self.bm25 or not self.chunk_ids:
            return []

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)
        
        # Max score for normalization
        max_score = max(scores) if len(scores) > 0 else 1.0
        if max_score <= 0:
            max_score = 1.0

        # Pair chunk with normalized score (0.0 to 1.0)
        scored_pairs = []
        for idx, score in enumerate(scores):
            if score > 0:
                cid = self.chunk_ids[idx]
                norm_score = min(float(score / max_score), 1.0)
                scored_pairs.append((self.chunks_map[cid], norm_score))

        scored_pairs.sort(key=lambda x: x[1], reverse=True)
        return scored_pairs[:top_k]
