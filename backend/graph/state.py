from typing import TypedDict, List, Optional, Any, Dict
from backend.models import RequirementItem, CompanyProfileSchema, ComplianceSummaryResponse, Citation
from backend.retrieval.hybrid_retriever import RetrievedPassage
from backend.guardrails.guardrail import GuardrailResult

class TenderWorkflowState(TypedDict):
    document_id: str
    document_title: str
    query: str
    intent: str  # REQUIREMENT_EXTRACTION, COMPLIANCE_EVALUATION, QA_RETRIEVAL, EXECUTIVE_REPORT
    
    # Retrieval Data
    retrieved_passages: List[Dict[str, Any]]
    
    # Structured Data
    requirements: List[Dict[str, Any]]
    profile: Optional[Dict[str, Any]]
    compliance_result: Optional[Dict[str, Any]]
    
    # Generation & Grounding
    raw_answer: str
    citations: List[Dict[str, Any]]
    guardrail_result: Optional[Dict[str, Any]]
    
    # Final Output
    final_response: str
    confidence: str
    status: str
    latency_ms: float
