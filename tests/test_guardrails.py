import pytest
from backend.guardrails.guardrail import TenderGuardrail
from backend.models import Citation
from backend.retrieval.hybrid_retriever import RetrievedPassage

def test_guardrail_blocks_when_no_passages():
    res = TenderGuardrail.apply("The bidder must submit an ISO 50001 certificate.", [], [])
    assert res.status == "BLOCKED"
    assert "No relevant clauses or evidence" in res.sanitized_answer
    assert "NO_EVIDENCE_FOUND" in res.flagged_issues

def test_guardrail_qualifies_on_low_confidence():
    passages = [
        RetrievedPassage(
            chunk_id="c1",
            document_id="d1",
            text="Unrelated text about municipal taxes.",
            page=1,
            section="General",
            heading="Intro",
            combined_score=0.25,  # Below threshold 0.35
            vector_score=0.25,
            bm25_score=0.0,
            match_type="VECTOR_ONLY"
        )
    ]
    citations = [Citation(chunk_id="c1", page=1, section="General", snippet="Unrelated")]
    
    res = TenderGuardrail.apply("Some uncertain claim", passages, citations, min_threshold=0.35)
    assert res.status == "QUALIFIED"
    assert "Low retrieval score" in res.sanitized_answer
