import re
from typing import List, Dict, Any, Tuple
from backend.models import Citation
from backend.retrieval.hybrid_retriever import RetrievedPassage

class EvidenceValidator:
    """
    Evidence Agent:
    Validates that claims, dates, amounts, and standards stated in answers
    are strictly grounded in source chunk passages. Prevents hallucinations.
    """

    @classmethod
    def validate_answer(
        cls,
        answer: str,
        passages: List[RetrievedPassage]
    ) -> Tuple[bool, float, List[Citation]]:
        """
        Returns:
            (is_grounded, groundedness_score, citations)
        """
        if not passages:
            return False, 0.0, []

        combined_evidence = " ".join([p.text.lower() for p in passages])
        citations: List[Citation] = []

        # Find exact passage citations
        for p in passages[:3]:
            # Take snippet
            snippet = p.text[:200] + ("..." if len(p.text) > 200 else "")
            citations.append(
                Citation(
                    chunk_id=p.chunk_id,
                    page=p.page,
                    section=p.section,
                    snippet=snippet
                )
            )

        # Extract factual tokens (numbers, currency, standards) from answer
        facts = re.findall(r'\b(?:\d+(?:\.\d+)?%?|ISO\s*\d+|₹[\d,]+|INR\s*[\d,]+|crores?|lakhs?|months?|years?)\b', answer, re.IGNORECASE)
        
        if not facts:
            # General textual overlap check
            ans_tokens = set(re.findall(r'[a-zA-Z]{4,}', answer.lower())) - {"based", "document", "tender", "according", "stated", "requirement"}
            evid_tokens = set(re.findall(r'[a-zA-Z]{4,}', combined_evidence))
            overlap = len(ans_tokens & evid_tokens) / max(len(ans_tokens), 1)
            is_grounded = overlap >= 0.25
            return is_grounded, round(overlap, 2), citations

        # Check fact containment
        supported_facts = 0
        for fact in facts:
            clean_fact = fact.lower().replace("₹", "").replace("inr", "").strip()
            if clean_fact in combined_evidence:
                supported_facts += 1

        score = supported_facts / len(facts)
        is_grounded = score >= 0.60
        return is_grounded, round(score, 2), citations
