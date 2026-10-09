import pytest
from pathlib import Path
from backend.ingestion.parser import DocumentParser
from backend.ingestion.chunker import SectionAwareChunker
from backend.retrieval.bm25_index import BM25KeywordIndex
from backend.retrieval.hybrid_retriever import HybridRetriever

@pytest.fixture
def sample_chunks():
    doc = DocumentParser.parse("documents/sample_smart_city_tender.pdf")
    chunker = SectionAwareChunker()
    return chunker.chunk_document("test-retrieval-doc", doc)

def test_bm25_exact_keyword_matching(sample_chunks):
    bm25 = BM25KeywordIndex()
    bm25.build_index(sample_chunks)

    # Test exact identifier search
    results = bm25.search("ISO 27001", top_k=3)
    assert len(results) > 0
    top_chunk, score = results[0]
    assert "27001" in top_chunk.text
    assert top_chunk.page == 3

    # Test numerical currency search
    emd_results = bm25.search("5,00,000", top_k=3)
    assert len(emd_results) > 0
    assert "5,00,000" in emd_results[0][0].text

def test_hybrid_retriever(sample_chunks):
    retriever = HybridRetriever()
    retriever.index_document("test-hybrid-doc", sample_chunks)

    passages = retriever.search("test-hybrid-doc", "turnover requirement for bidding", top_k=3)
    assert len(passages) > 0
    top_p = passages[0]
    assert top_p.combined_score > 0
    assert top_p.page == 2
    assert "turnover" in top_p.text.lower()
