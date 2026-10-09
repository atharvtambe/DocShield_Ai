import pytest
from backend.models import RequirementItem, CompanyProfileSchema
from backend.agents.requirement_agent import RequirementAgent
from backend.agents.router import QueryRouter
from backend.agents.evidence_agent import EvidenceValidator
from backend.ingestion.parser import DocumentParser
from backend.ingestion.chunker import SectionAwareChunker
from backend.retrieval.hybrid_retriever import RetrievedPassage

def test_query_router():
    assert QueryRouter.route("Extract all mandatory criteria") == "REQUIREMENT_EXTRACTION"
    assert QueryRouter.route("Can my company bid on this?") == "COMPLIANCE_EVALUATION"
    assert QueryRouter.route("What is the EMD fee?") == "QA_RETRIEVAL"
    assert QueryRouter.route("Generate executive bid report") == "EXECUTIVE_REPORT"

def test_requirement_agent_extraction():
    doc = DocumentParser.parse("documents/sample_smart_city_tender.pdf")
    chunker = SectionAwareChunker()
    chunks = chunker.chunk_document("test-doc-req", doc)

    agent = RequirementAgent()
    reqs = agent.extract_from_chunks("test-doc-req", chunks)

    assert len(reqs) >= 4
    categories = set(r.category for r in reqs)
    assert "Eligibility" in categories or "Financial" in categories or "Certifications" in categories
    
    # Verify provenance preserved in requirements
    for r in reqs:
        assert r.page in [1, 2, 3, 4]
        assert len(r.evidence_chunk_ids) > 0
        assert r.confidence in ["high", "medium", "low"]

def test_evidence_validator():
    passages = [
        RetrievedPassage(
            chunk_id="chunk_1",
            document_id="doc_1",
            text="The bidder must have at least 5 years of experience and annual turnover of 15 crores.",
            page=2,
            section="Eligibility",
            heading="Experience",
            combined_score=0.85,
            vector_score=0.8,
            bm25_score=0.9,
            match_type="HYBRID"
        )
    ]

    # Grounded claim
    answer = "The requirement specifies 5 years of experience and turnover of 15 crores."
    is_grounded, score, citations = EvidenceValidator.validate_answer(answer, passages)
    assert is_grounded is True
    assert score >= 0.5
    assert len(citations) == 1
    assert citations[0].page == 2
