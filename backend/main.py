import os
import json
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db, init_db, SessionLocal
from backend.models import (
    TenderDocumentORM,
    TenderChunkORM,
    RequirementORM,
    CompanyProfileORM,
    ComplianceResultORM,
    EvaluationRunORM,
    RequirementItem,
    CompanyProfileSchema,
    QARequest,
    QAResponse,
    Citation,
    ComplianceSummaryResponse,
    ChunkProvenance
)
from backend.ingestion.parser import DocumentParser
from backend.ingestion.chunker import SectionAwareChunker
from backend.retrieval.hybrid_retriever import HybridRetriever
from backend.agents.requirement_agent import RequirementAgent
from backend.agents.compliance_agent import ComplianceAgent
from backend.agents.llm_client import llm_client
from backend.graph.workflow import TenderWorkflowManager
from backend.reporting.generator import ReportGenerator
from backend.evaluation.evaluator import TenderEvaluator

# Initialize database
init_db()

# Initialize core services
chunker = SectionAwareChunker()
retriever = HybridRetriever()
workflow_manager = TenderWorkflowManager(retriever)
evaluator = TenderEvaluator(workflow_manager)
req_agent = RequirementAgent()
comp_agent = ComplianceAgent()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Agentic Tender & Compliance Intelligence Platform"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Seed default company profile if not present
def ensure_default_profile():
    db = SessionLocal()
    try:
        prof = db.query(CompanyProfileORM).filter(CompanyProfileORM.id == "default-profile").first()
        if not prof:
            default_p = CompanyProfileORM(
                id="default-profile",
                company_name="AlphaTech Solutions Pvt Ltd",
                turnover_cr=18.5,
                experience_years=7.0,
                certifications=json.dumps(["ISO 9001", "ISO 27001", "CMMI Level 3"]),
                technical_capabilities=json.dumps(["Cloud Architecture", "Kubernetes", "AI / Computer Vision", "PostgreSQL", "Cybersecurity Audit"]),
                past_projects=json.dumps([
                    {"name": "State Smart Surveillance", "client": "Dept of IT", "value_cr": 8.5, "year": 2023},
                    {"name": "Municipal IoT Portal", "client": "Smart City Mission", "value_cr": 6.2, "year": 2024}
                ]),
                location="Bangalore, India",
                employee_count=85
            )
            db.add(default_p)
            db.commit()
    finally:
        db.close()

ensure_default_profile()


# ==========================================
# Health & Status
# ==========================================
@app.get("/api/health")
def get_health(db: Session = Depends(get_db)):
    doc_count = db.query(TenderDocumentORM).count()
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "llm_provider": llm_client.get_provider_name(),
        "cloud_llm_active": llm_client.is_cloud_enabled(),
        "total_documents": doc_count
    }


# ==========================================
# Tender Management & Ingestion
# ==========================================
def _process_and_store_tender(file_path: Path, filename: str, title: str, db: Session) -> TenderDocumentORM:
    # 1. Parse document
    parsed = DocumentParser.parse(file_path)
    
    # 2. Create DB record
    doc_id = str(uuid.uuid4())
    doc_record = TenderDocumentORM(
        id=doc_id,
        title=title,
        filename=filename,
        file_path=str(file_path),
        file_type=parsed.file_type,
        file_size_bytes=file_path.stat().st_size,
        page_count=parsed.page_count,
        chunk_count=0,
        status="processing"
    )
    db.add(doc_record)
    db.commit()

    # 3. Section and page-aware chunking preserving provenance
    chunks = chunker.chunk_document(doc_id, parsed)
    doc_record.chunk_count = len(chunks)

    # 4. Store chunks in DB
    chunk_orms = []
    for c in chunks:
        chunk_orms.append(
            TenderChunkORM(
                chunk_id=c.chunk_id,
                document_id=doc_id,
                text=c.text,
                page=c.page,
                section=c.section,
                heading=c.heading,
                metadata_json=json.dumps(c.metadata)
            )
        )
    db.bulk_save_objects(chunk_orms)
    db.commit()

    # 5. Build Hybrid Retrieval Indices (Vector Store + BM25)
    retriever.index_document(doc_id, chunks)

    # 6. Extract structured requirements
    req_items = req_agent.extract_from_chunks(doc_id, chunks)
    for r in req_items:
        r_orm = RequirementORM(
            id=str(uuid.uuid4()),
            document_id=doc_id,
            category=r.category,
            description=r.description,
            value=r.value,
            mandatory=r.mandatory,
            page=r.page,
            evidence_chunk_ids=json.dumps(r.evidence_chunk_ids),
            confidence=r.confidence,
            raw_quote=r.raw_quote or ""
        )
        db.add(r_orm)

    doc_record.status = "ready"
    db.commit()
    db.refresh(doc_record)
    return doc_record


@app.post("/api/tenders/upload")
async def upload_tender(file: UploadFile = File(...), title: Optional[str] = Form(None), db: Session = Depends(get_db)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in [".pdf", ".docx", ".doc", ".txt"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Supported: .pdf, .docx, .txt")

    save_path = settings.UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    doc_title = title if title and title.strip() else Path(file.filename).stem.replace("_", " ").title()
    doc_record = _process_and_store_tender(save_path, file.filename, doc_title, db)

    return {
        "id": doc_record.id,
        "title": doc_record.title,
        "filename": doc_record.filename,
        "pages": doc_record.page_count,
        "chunks": doc_record.chunk_count,
        "status": doc_record.status
    }


@app.post("/api/tenders/sample/load")
def load_sample_tender(sample_type: str = Query("smart_city", description="smart_city or highway"), db: Session = Depends(get_db)):
    """Loads a pre-packaged realistic tender for instant 1-click exploration."""
    filename = "sample_smart_city_tender.pdf" if sample_type == "smart_city" else "sample_highway_tender.docx"
    sample_path = settings.DOCUMENTS_DIR / filename
    
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail=f"Sample document {filename} not found.")

    title = "Smart City Cloud Platform & Video Analytics RFP" if sample_type == "smart_city" else "State Highway Surveillance & Traffic RFP"
    
    # Check if already loaded
    existing = db.query(TenderDocumentORM).filter(TenderDocumentORM.filename == filename).first()
    if existing:
        return {
            "id": existing.id,
            "title": existing.title,
            "filename": existing.filename,
            "pages": existing.page_count,
            "chunks": existing.chunk_count,
            "status": existing.status,
            "message": "Sample tender already loaded."
        }

    doc_record = _process_and_store_tender(sample_path, filename, title, db)
    return {
        "id": doc_record.id,
        "title": doc_record.title,
        "filename": doc_record.filename,
        "pages": doc_record.page_count,
        "chunks": doc_record.chunk_count,
        "status": doc_record.status,
        "message": "Sample tender loaded and indexed successfully."
    }


@app.get("/api/tenders")
def list_tenders(db: Session = Depends(get_db)):
    docs = db.query(TenderDocumentORM).order_by(TenderDocumentORM.created_at.desc()).all()
    out = []
    for d in docs:
        req_count = db.query(RequirementORM).filter(RequirementORM.document_id == d.id).count()
        latest_comp = db.query(ComplianceResultORM).filter(ComplianceResultORM.document_id == d.id).order_by(ComplianceResultORM.created_at.desc()).first()
        out.append({
            "id": d.id,
            "title": d.title,
            "filename": d.filename,
            "file_type": d.file_type,
            "page_count": d.page_count,
            "chunk_count": d.chunk_count,
            "requirements_count": req_count,
            "readiness_score": latest_comp.overall_score if latest_comp else None,
            "overall_status": latest_comp.overall_status if latest_comp else "NOT_EVALUATED",
            "created_at": d.created_at.isoformat()
        })
    return out


@app.get("/api/tenders/{tender_id}")
def get_tender_detail(tender_id: str, db: Session = Depends(get_db)):
    doc = db.query(TenderDocumentORM).filter(TenderDocumentORM.id == tender_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Tender not found")

    req_count = db.query(RequirementORM).filter(RequirementORM.document_id == doc.id).count()
    chunks = db.query(TenderChunkORM).filter(TenderChunkORM.document_id == doc.id).all()
    
    sections = sorted(list(set(c.section for c in chunks)))

    return {
        "id": doc.id,
        "title": doc.title,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "page_count": doc.page_count,
        "chunk_count": doc.chunk_count,
        "requirements_count": req_count,
        "sections": sections,
        "created_at": doc.created_at.isoformat()
    }


@app.delete("/api/tenders/{tender_id}")
def delete_tender(tender_id: str, db: Session = Depends(get_db)):
    doc = db.query(TenderDocumentORM).filter(TenderDocumentORM.id == tender_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Tender not found")

    db.query(RequirementORM).filter(RequirementORM.document_id == tender_id).delete()
    db.query(TenderChunkORM).filter(TenderChunkORM.document_id == tender_id).delete()
    db.query(ComplianceResultORM).filter(ComplianceResultORM.document_id == tender_id).delete()
    db.delete(doc)
    db.commit()

    retriever.vector_store.delete_document_chunks(tender_id)
    return {"status": "success", "message": f"Tender {tender_id} deleted."}


# ==========================================
# Requirement Extraction Endpoints
# ==========================================
@app.get("/api/tenders/{tender_id}/requirements")
def get_requirements(tender_id: str, category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(RequirementORM).filter(RequirementORM.document_id == tender_id)
    if category:
        query = query.filter(RequirementORM.category == category)
    
    reqs = query.order_by(RequirementORM.page.asc()).all()
    
    # Category counts summary
    all_reqs = db.query(RequirementORM).filter(RequirementORM.document_id == tender_id).all()
    category_counts: Dict[str, int] = {}
    mandatory_count = 0
    optional_count = 0
    for r in all_reqs:
        category_counts[r.category] = category_counts.get(r.category, 0) + 1
        if r.mandatory:
            mandatory_count += 1
        else:
            optional_count += 1

    items = []
    for r in reqs:
        evidence_ids = []
        try:
            evidence_ids = json.loads(r.evidence_chunk_ids)
        except Exception:
            pass

        items.append({
            "id": r.id,
            "category": r.category,
            "description": r.description,
            "value": r.value,
            "mandatory": r.mandatory,
            "page": r.page,
            "confidence": r.confidence,
            "raw_quote": r.raw_quote,
            "evidence_chunk_ids": evidence_ids
        })

    return {
        "total": len(all_reqs),
        "mandatory_count": mandatory_count,
        "optional_count": optional_count,
        "category_counts": category_counts,
        "items": items
    }


# ==========================================
# Company Profile CRUD
# ==========================================
@app.get("/api/profile")
def get_company_profile(db: Session = Depends(get_db)):
    prof = db.query(CompanyProfileORM).filter(CompanyProfileORM.id == "default-profile").first()
    if not prof:
        ensure_default_profile()
        prof = db.query(CompanyProfileORM).filter(CompanyProfileORM.id == "default-profile").first()

    return {
        "id": prof.id,
        "company_name": prof.company_name,
        "turnover_cr": prof.turnover_cr,
        "experience_years": prof.experience_years,
        "certifications": json.loads(prof.certifications),
        "technical_capabilities": json.loads(prof.technical_capabilities),
        "past_projects": json.loads(prof.past_projects),
        "location": prof.location,
        "employee_count": prof.employee_count
    }


@app.post("/api/profile")
def update_company_profile(data: CompanyProfileSchema, db: Session = Depends(get_db)):
    prof = db.query(CompanyProfileORM).filter(CompanyProfileORM.id == "default-profile").first()
    if not prof:
        prof = CompanyProfileORM(id="default-profile")
        db.add(prof)

    prof.company_name = data.company_name
    prof.turnover_cr = data.turnover_cr
    prof.experience_years = data.experience_years
    prof.certifications = json.dumps(data.certifications)
    prof.technical_capabilities = json.dumps(data.technical_capabilities)
    prof.past_projects = json.dumps(data.past_projects)
    prof.location = data.location or "India"
    prof.employee_count = data.employee_count or 50

    db.commit()
    return {"status": "success", "message": "Company profile updated"}


# ==========================================
# Compliance & Bid-Readiness Check
# ==========================================
@app.post("/api/tenders/{tender_id}/compliance")
def evaluate_compliance(tender_id: str, db: Session = Depends(get_db)):
    doc = db.query(TenderDocumentORM).filter(TenderDocumentORM.id == tender_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Tender not found")

    prof = db.query(CompanyProfileORM).filter(CompanyProfileORM.id == "default-profile").first()
    profile_schema = CompanyProfileSchema(
        id=prof.id,
        company_name=prof.company_name,
        turnover_cr=prof.turnover_cr,
        experience_years=prof.experience_years,
        certifications=json.loads(prof.certifications),
        technical_capabilities=json.loads(prof.technical_capabilities),
        past_projects=json.loads(prof.past_projects),
        location=prof.location,
        employee_count=prof.employee_count
    )

    req_orms = db.query(RequirementORM).filter(RequirementORM.document_id == tender_id).all()
    req_items = [
        RequirementItem(
            id=r.id,
            category=r.category,
            description=r.description,
            value=r.value,
            mandatory=r.mandatory,
            page=r.page,
            confidence=r.confidence,
            raw_quote=r.raw_quote,
            evidence_chunk_ids=json.loads(r.evidence_chunk_ids or "[]")
        )
        for r in req_orms
    ]

    result = comp_agent.evaluate_compliance(tender_id, doc.title, req_items, profile_schema)

    # Save to database
    items_json_str = json.dumps([it.model_dump() for it in result.items])
    res_orm = ComplianceResultORM(
        document_id=tender_id,
        profile_id=prof.id,
        overall_status=result.overall_status,
        overall_score=result.readiness_score,
        total_requirements=result.total_requirements,
        satisfied_count=result.satisfied_count,
        missing_count=result.missing_count,
        risky_count=result.risky_count,
        clarification_count=result.clarification_count,
        summary_text=result.summary_text,
        items_json=items_json_str
    )
    db.add(res_orm)
    db.commit()

    return result.model_dump()


# ==========================================
# Evidence-Backed AI Chat (LangGraph)
# ==========================================
@app.post("/api/tenders/{tender_id}/chat", response_model=QAResponse)
def chat_with_tender(tender_id: str, payload: QARequest, db: Session = Depends(get_db)):
    doc = db.query(TenderDocumentORM).filter(TenderDocumentORM.id == tender_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Tender not found")

    # Ensure BM25 is loaded in memory for this doc
    chunks = db.query(TenderChunkORM).filter(TenderChunkORM.document_id == tender_id).all()
    chunk_provs = [
        ChunkProvenance(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            text=c.text,
            page=c.page,
            section=c.section,
            heading=c.heading or "",
            metadata=json.loads(c.metadata_json or "{}")
        )
        for c in chunks
    ]
    retriever.get_or_create_bm25(tender_id, chunk_provs)

    # Execute LangGraph Agentic Workflow
    workflow_out = workflow_manager.execute(
        document_id=tender_id,
        query=payload.question,
        document_title=doc.title,
        intent="QA_RETRIEVAL"
    )

    citations = [Citation(**c) for c in workflow_out.get("citations", [])]

    return QAResponse(
        answer=workflow_out.get("final_response", ""),
        citations=citations,
        confidence=workflow_out.get("confidence", "HIGH"),
        guardrail_status=workflow_out.get("status", "APPROVED"),
        latency_ms=workflow_out.get("latency_ms", 0.0)
    )


# ==========================================
# Report Generation
# ==========================================
@app.get("/api/tenders/{tender_id}/report")
def get_report(tender_id: str, format: str = Query("json", description="json, markdown, or html"), db: Session = Depends(get_db)):
    doc = db.query(TenderDocumentORM).filter(TenderDocumentORM.id == tender_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Tender not found")

    prof = db.query(CompanyProfileORM).filter(CompanyProfileORM.id == "default-profile").first()
    profile_schema = CompanyProfileSchema(
        id=prof.id,
        company_name=prof.company_name,
        turnover_cr=prof.turnover_cr,
        experience_years=prof.experience_years,
        certifications=json.loads(prof.certifications),
        technical_capabilities=json.loads(prof.technical_capabilities),
        past_projects=json.loads(prof.past_projects),
        location=prof.location,
        employee_count=prof.employee_count
    )

    req_orms = db.query(RequirementORM).filter(RequirementORM.document_id == tender_id).all()
    req_items = [
        RequirementItem(
            id=r.id,
            category=r.category,
            description=r.description,
            value=r.value,
            mandatory=r.mandatory,
            page=r.page,
            confidence=r.confidence,
            raw_quote=r.raw_quote,
            evidence_chunk_ids=json.loads(r.evidence_chunk_ids or "[]")
        )
        for r in req_orms
    ]

    comp_res = comp_agent.evaluate_compliance(tender_id, doc.title, req_items, profile_schema)

    if format == "markdown":
        md = ReportGenerator.generate_markdown(doc.title, comp_res, profile_schema)
        return PlainTextResponse(content=md, media_type="text/markdown")
    elif format == "html":
        html = ReportGenerator.generate_html(doc.title, comp_res, profile_schema)
        return HTMLResponse(content=html)
    
    md_text = ReportGenerator.generate_markdown(doc.title, comp_res, profile_schema)
    return {
        "document_title": doc.title,
        "compliance": comp_res.model_dump(),
        "markdown_report": md_text
    }


# ==========================================
# Evaluation Suite Endpoints
# ==========================================
@app.post("/api/evaluation/run")
def run_evaluation(tender_id: Optional[str] = None, db: Session = Depends(get_db)):
    target_id = tender_id
    if not target_id:
        doc = db.query(TenderDocumentORM).first()
        if not doc:
            raise HTTPException(status_code=400, detail="No tender documents found. Please load or upload a tender first.")
        target_id = doc.id

    # Ensure BM25 is prepared
    chunks = db.query(TenderChunkORM).filter(TenderChunkORM.document_id == target_id).all()
    chunk_provs = [
        ChunkProvenance(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            text=c.text,
            page=c.page,
            section=c.section,
            heading=c.heading or "",
            metadata=json.loads(c.metadata_json or "{}")
        )
        for c in chunks
    ]
    retriever.get_or_create_bm25(target_id, chunk_provs)

    eval_result = evaluator.run_evaluation(target_id)

    # Save run in DB
    run_orm = EvaluationRunORM(
        document_id=target_id,
        total_questions=eval_result["total_questions"],
        retrieval_recall=eval_result["retrieval_recall_pct"],
        answer_accuracy=eval_result["answer_accuracy_pct"],
        citation_accuracy=eval_result["citation_accuracy_pct"],
        hallucination_rate=eval_result["hallucination_rate_pct"],
        avg_latency_ms=eval_result["avg_latency_ms"],
        details_json=json.dumps(eval_result["detailed_results"])
    )
    db.add(run_orm)
    db.commit()

    return eval_result


@app.get("/api/evaluation/history")
def get_evaluation_history(db: Session = Depends(get_db)):
    runs = db.query(EvaluationRunORM).order_by(EvaluationRunORM.created_at.desc()).limit(10).all()
    return [
        {
            "id": r.id,
            "document_id": r.document_id,
            "total_questions": r.total_questions,
            "retrieval_recall_pct": r.retrieval_recall,
            "answer_accuracy_pct": r.answer_accuracy,
            "citation_accuracy_pct": r.citation_accuracy,
            "hallucination_rate_pct": r.hallucination_rate,
            "avg_latency_ms": r.avg_latency_ms,
            "created_at": r.created_at.isoformat()
        }
        for r in runs
    ]
