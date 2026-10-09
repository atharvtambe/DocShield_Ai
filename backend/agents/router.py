import re
from typing import Literal
from backend.agents.llm_client import llm_client

IntentType = Literal["REQUIREMENT_EXTRACTION", "COMPLIANCE_EVALUATION", "QA_RETRIEVAL", "EXECUTIVE_REPORT"]

class QueryRouter:
    """
    LangGraph Router Agent:
    Classifies the user's intent to select the appropriate specialized agent pipeline.
    """

    @classmethod
    def route(cls, query: str) -> IntentType:
        q = query.lower().strip()

        # Check for report requests
        if "report" in q or "summary" in q or ("executive" in q and "bid" in q):
            return "EXECUTIVE_REPORT"

        # Check for compliance / eligibility check
        if any(w in q for w in ["compliance", "bid readiness", "can we bid", "can my company", "are we eligible", "qualify", "match profile", "evaluate company", "eligibility"]):
            return "COMPLIANCE_EVALUATION"

        # Check for full requirement extraction
        if any(w in q for w in ["extract", "requirements", "criteria", "mandatory conditions"]):
            return "REQUIREMENT_EXTRACTION"

        # Default to QA Retrieval for specific questions (e.g., "What is the EMD?", "Which ISO is needed?")
        return "QA_RETRIEVAL"
