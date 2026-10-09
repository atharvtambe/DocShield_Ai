import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey
from pydantic import BaseModel, Field
from backend.database import Base

# ==========================================
# SQLAlchemy ORM Models
# ==========================================

class TenderDocumentORM(Base):
    __tablename__ = "tender_documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(32), default="pdf")
    file_size_bytes = Column(Integer, default=0)
    page_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    status = Column(String(32), default="ready")  # uploaded, processing, ready, error
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class TenderChunkORM(Base):
    __tablename__ = "tender_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chunk_id = Column(String(64), index=True, nullable=False)
    document_id = Column(String(36), ForeignKey("tender_documents.id"), index=True, nullable=False)
    text = Column(Text, nullable=False)
    page = Column(Integer, nullable=False)
    section = Column(String(128), default="General")
    heading = Column(String(255), default="")
    metadata_json = Column(Text, default="{}")

class RequirementORM(Base):
    __tablename__ = "requirements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("tender_documents.id"), index=True, nullable=False)
    category = Column(String(64), nullable=False)  # Eligibility, Technical, Financial, Certifications, Documentation, Delivery, Evaluation
    description = Column(Text, nullable=False)
    value = Column(String(255), default="")
    mandatory = Column(Boolean, default=True)
    page = Column(Integer, nullable=False)
    evidence_chunk_ids = Column(Text, default="[]")  # JSON list
    confidence = Column(String(32), default="high")  # high, medium, low
    raw_quote = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class CompanyProfileORM(Base):
    __tablename__ = "company_profiles"

    id = Column(String(36), primary_key=True, default="default-profile")
    company_name = Column(String(255), default="AlphaTech Solutions Pvt Ltd")
    turnover_cr = Column(Float, default=18.5)
    experience_years = Column(Float, default=7.0)
    certifications = Column(Text, default='["ISO 9001", "ISO 27001", "CMMI Level 3"]')  # JSON list
    technical_capabilities = Column(Text, default='["Cloud Architecture", "Kubernetes", "AI / Computer Vision", "PostgreSQL", "Cybersecurity Audit"]')  # JSON list
    past_projects = Column(Text, default='[{"name": "State Smart Surveillance", "client": "Dept of IT", "value_cr": 8.5, "year": 2023}]')  # JSON list
    location = Column(String(128), default="Bangalore, India")
    employee_count = Column(Integer, default=85)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ComplianceResultORM(Base):
    __tablename__ = "compliance_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("tender_documents.id"), index=True, nullable=False)
    profile_id = Column(String(36), default="default-profile")
    overall_status = Column(String(32), default="PARTIAL")  # QUALIFIED, PARTIAL, DISQUALIFIED
    overall_score = Column(Float, default=0.0)  # 0 to 100
    total_requirements = Column(Integer, default=0)
    satisfied_count = Column(Integer, default=0)
    missing_count = Column(Integer, default=0)
    risky_count = Column(Integer, default=0)
    clarification_count = Column(Integer, default=0)
    summary_text = Column(Text, default="")
    items_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class EvaluationRunORM(Base):
    __tablename__ = "evaluation_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), nullable=True)
    total_questions = Column(Integer, default=0)
    retrieval_recall = Column(Float, default=0.0)
    answer_accuracy = Column(Float, default=0.0)
    citation_accuracy = Column(Float, default=0.0)
    hallucination_rate = Column(Float, default=0.0)
    avg_latency_ms = Column(Float, default=0.0)
    details_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)

# ==========================================
# Pydantic Schemas for API & Workflows
# ==========================================

class ChunkProvenance(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    page: int
    section: str = "General"
    heading: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

class RequirementItem(BaseModel):
    id: Optional[str] = None
    category: str = "Eligibility"
    description: str
    value: str = ""
    mandatory: bool = True
    page: int
    evidence_chunk_ids: List[str] = Field(default_factory=list)
    confidence: str = "high"
    raw_quote: Optional[str] = None

class ComplianceItem(BaseModel):
    requirement_id: Optional[str] = None
    category: str
    requirement_text: str
    mandatory: bool
    page: int
    company_value: str
    required_value: str
    status: str  # SATISFIED, MISSING, RISKY, CLARIFICATION_NEEDED
    reason: str
    evidence_snippet: str = ""

class CompanyProfileSchema(BaseModel):
    id: Optional[str] = "default-profile"
    company_name: str
    turnover_cr: float
    experience_years: float
    certifications: List[str]
    technical_capabilities: List[str]
    past_projects: List[Dict[str, Any]] = Field(default_factory=list)
    location: Optional[str] = "India"
    employee_count: Optional[int] = 50

class QARequest(BaseModel):
    document_id: str
    question: str
    include_citations: bool = True

class Citation(BaseModel):
    chunk_id: str
    page: int
    section: str
    snippet: str

class QAResponse(BaseModel):
    answer: str
    citations: List[Citation]
    confidence: str
    guardrail_status: str  # APPROVED, QUALIFIED, BLOCKED
    latency_ms: float

class ComplianceSummaryResponse(BaseModel):
    document_id: str
    document_title: str
    overall_status: str  # QUALIFIED, PARTIAL, DISQUALIFIED
    readiness_score: float  # 0 to 100
    total_requirements: int
    satisfied_count: int
    missing_count: int
    risky_count: int
    clarification_count: int
    summary_text: str
    items: List[ComplianceItem]
