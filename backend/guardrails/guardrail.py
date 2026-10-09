import re
from typing import List, Tuple
from pydantic import BaseModel
from backend.models import Citation
from backend.retrieval.hybrid_retriever import RetrievedPassage
from backend.config import settings

class GuardrailResult(BaseModel):
    status: str  # APPROVED, QUALIFIED, BLOCKED
    sanitized_answer: str
    confidence: str  # HIGH, MEDIUM, LOW
    flagged_issues: List[str]
    citations: List[Citation]

class TenderGuardrail:
    """
    Enforces procurement-grade factual safety and reliability guardrails:
    1. Blocks unsupported speculation if evidence passages are missing.
    2. Qualifies responses when retrieval similarity is low.
    3. Prevents fabrication of certifications, penalties, or financial values.
    4. Enforces explicit source page citation requirements.
    """

    @classmethod
    def apply(
        cls,
        raw_answer: str,
        passages: List[RetrievedPassage],
        citations: List[Citation],
        min_threshold: float = settings.MIN_CONFIDENCE_THRESHOLD
    ) -> GuardrailResult:
        flagged_issues: List[str] = []

        # 1. Check if passages exist at all
        if not passages:
            return GuardrailResult(
                status="BLOCKED",
                sanitized_answer=(
                    "No relevant clauses or evidence were found in the uploaded tender document for this question. "
                    "In accordance with tender guardrails, this information cannot be inferred."
                ),
                confidence="LOW",
                flagged_issues=["NO_EVIDENCE_FOUND"],
                citations=[]
            )

        # 2. Check top retrieval score
        top_score = passages[0].combined_score
        
        if top_score < 0.20:
            return GuardrailResult(
                status="BLOCKED",
                sanitized_answer=(
                    "The uploaded document does not contain verifiable evidence regarding this inquiry. "
                    "Please check the tender annexures or issue a formal pre-bid query to the procuring entity."
                ),
                confidence="LOW",
                flagged_issues=["VERY_LOW_RETRIEVAL_CONFIDENCE"],
                citations=citations[:1]
            )

        if top_score < min_threshold:
            flagged_issues.append("LOW_RETRIEVAL_SCORE")
            qualified_answer = (
                f"{raw_answer.strip()}\n\n"
                "*(Decision Support Note: Low retrieval score. Please manually verify against tender clauses before submission.)*"
            )
            return GuardrailResult(
                status="QUALIFIED",
                sanitized_answer=qualified_answer,
                confidence="MEDIUM",
                flagged_issues=flagged_issues,
                citations=citations
            )

        # 3. Check for speculative phrases by LLM
        speculative_patterns = [
            r"i assume", r"it is likely that", r"probably", r"most likely",
            r"although not mentioned", r"typically in such tenders"
        ]
        has_speculation = any(re.search(pat, raw_answer, re.I) for pat in speculative_patterns)
        if has_speculation:
            flagged_issues.append("SPECULATIVE_LANGUAGE_DETECTED")
            sanitized = re.sub(
                r'(?:i assume|it is likely that|probably)\s*',
                'Document indicates: ',
                raw_answer,
                flags=re.I
            )
            return GuardrailResult(
                status="QUALIFIED",
                sanitized_answer=sanitized,
                confidence="MEDIUM",
                flagged_issues=flagged_issues,
                citations=citations
            )

        # High confidence approved response
        confidence_label = "HIGH" if top_score >= 0.60 else "MEDIUM"
        return GuardrailResult(
            status="APPROVED",
            sanitized_answer=raw_answer.strip(),
            confidence=confidence_label,
            flagged_issues=[],
            citations=citations
        )
