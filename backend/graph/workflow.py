import time
from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END

from backend.graph.state import TenderWorkflowState
from backend.agents.router import QueryRouter
from backend.agents.requirement_agent import RequirementAgent
from backend.agents.compliance_agent import ComplianceAgent
from backend.agents.evidence_agent import EvidenceValidator
from backend.agents.llm_client import llm_client
from backend.guardrails.guardrail import TenderGuardrail
from backend.retrieval.hybrid_retriever import HybridRetriever, RetrievedPassage
from backend.models import RequirementItem, CompanyProfileSchema, Citation

class TenderWorkflowManager:
    """
    Orchestrates the LangGraph Agentic Workflow for TenderSense AI:
    START -> Router -> [Retrieval] -> [Requirement / Compliance / QA Analysis] -> Evidence Validator -> Guardrail -> END
    """

    def __init__(self, hybrid_retriever: HybridRetriever):
        self.retriever = hybrid_retriever
        self.req_agent = RequirementAgent()
        self.comp_agent = ComplianceAgent()
        self.workflow = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(TenderWorkflowState)

        # Register nodes
        builder.add_node("router", self._node_router)
        builder.add_node("retrieval", self._node_retrieval)
        builder.add_node("requirement_analysis", self._node_requirement_analysis)
        builder.add_node("compliance_analysis", self._node_compliance_analysis)
        builder.add_node("qa_analysis", self._node_qa_analysis)
        builder.add_node("evidence_validator", self._node_evidence_validator)
        builder.add_node("guardrail", self._node_guardrail)

        # Wire edges
        builder.add_edge(START, "router")
        builder.add_edge("router", "retrieval")

        # Conditional branching from retrieval based on intent
        builder.add_conditional_edges(
            "retrieval",
            self._route_after_retrieval,
            {
                "requirement": "requirement_analysis",
                "compliance": "compliance_analysis",
                "qa": "qa_analysis"
            }
        )

        # Convergence to evidence validation and guardrails
        builder.add_edge("requirement_analysis", "evidence_validator")
        builder.add_edge("compliance_analysis", "evidence_validator")
        builder.add_edge("qa_analysis", "evidence_validator")

        builder.add_edge("evidence_validator", "guardrail")
        builder.add_edge("guardrail", END)

        return builder.compile()

    def _node_router(self, state: TenderWorkflowState) -> Dict[str, Any]:
        intent = state.get("intent")
        if not intent:
            intent = QueryRouter.route(state["query"])
        return {"intent": intent}

    def _node_retrieval(self, state: TenderWorkflowState) -> Dict[str, Any]:
        doc_id = state["document_id"]
        query = state["query"]
        top_k = 8 if state["intent"] in ["REQUIREMENT_EXTRACTION", "COMPLIANCE_EVALUATION"] else 5

        passages = self.retriever.search(doc_id, query, top_k=top_k)
        passages_dicts = [p.model_dump() for p in passages]
        return {"retrieved_passages": passages_dicts}

    def _route_after_retrieval(self, state: TenderWorkflowState) -> str:
        intent = state["intent"]
        if intent == "REQUIREMENT_EXTRACTION":
            return "requirement"
        elif intent in ["COMPLIANCE_EVALUATION", "EXECUTIVE_REPORT"]:
            return "compliance"
        return "qa"

    def _node_requirement_analysis(self, state: TenderWorkflowState) -> Dict[str, Any]:
        # If requirements already provided in state, keep them
        if state.get("requirements"):
            return {}

        passages = [RetrievedPassage(**p) for p in state["retrieved_passages"]]
        from backend.models import ChunkProvenance
        chunks = [
            ChunkProvenance(
                chunk_id=p.chunk_id,
                document_id=p.document_id,
                text=p.text,
                page=p.page,
                section=p.section,
                heading=p.heading
            )
            for p in passages
        ]
        items = self.req_agent.extract_from_chunks(state["document_id"], chunks)
        items_dict = [it.model_dump() for it in items]
        
        summary_lines = [f"- [{it.category}] {it.description} (Req: {it.value}, Page {it.page})" for it in items[:6]]
        raw_ans = "Extracted Structured Requirements:\n" + "\n".join(summary_lines)
        return {
            "requirements": items_dict,
            "raw_answer": raw_ans
        }

    def _node_compliance_analysis(self, state: TenderWorkflowState) -> Dict[str, Any]:
        # Ensure we have requirements
        reqs_raw = state.get("requirements") or []
        req_items = [RequirementItem(**r) for r in reqs_raw]

        if not req_items:
            # Extract from current passages
            passages = [RetrievedPassage(**p) for p in state["retrieved_passages"]]
            from backend.models import ChunkProvenance
            chunks = [
                ChunkProvenance(
                    chunk_id=p.chunk_id,
                    document_id=p.document_id,
                    text=p.text,
                    page=p.page,
                    section=p.section,
                    heading=p.heading
                )
                for p in passages
            ]
            req_items = self.req_agent.extract_from_chunks(state["document_id"], chunks)
            state["requirements"] = [r.model_dump() for r in req_items]

        # Use profile from state or default
        prof_dict = state.get("profile") or {
            "company_name": "AlphaTech Solutions Pvt Ltd",
            "turnover_cr": 18.5,
            "experience_years": 7.0,
            "certifications": ["ISO 9001", "ISO 27001", "CMMI Level 3"],
            "technical_capabilities": ["Cloud Architecture", "Kubernetes", "AI / Computer Vision"],
            "past_projects": []
        }
        profile = CompanyProfileSchema(**prof_dict)
        doc_title = state.get("document_title", "Tender Document")

        comp_res = self.comp_agent.evaluate_compliance(state["document_id"], doc_title, req_items, profile)
        
        answer_text = (
            f"Compliance Status: {comp_res.overall_status} (Score: {comp_res.readiness_score}%)\n"
            f"• Satisfied: {comp_res.satisfied_count}\n"
            f"• Missing: {comp_res.missing_count}\n"
            f"• Risky: {comp_res.risky_count}\n"
            f"• Clarification Needed: {comp_res.clarification_count}\n\n"
            f"Summary: {comp_res.summary_text}"
        )

        return {
            "compliance_result": comp_res.model_dump(),
            "raw_answer": answer_text
        }

    def _node_qa_analysis(self, state: TenderWorkflowState) -> Dict[str, Any]:
        query = state["query"]
        passages = [RetrievedPassage(**p) for p in state["retrieved_passages"]]
        
        context_parts = []
        for p in passages:
            context_parts.append(f"[Page {p.page}] [Chunk {p.chunk_id}] {p.text}")
        context_str = "\n\n".join(context_parts)

        prompt = f"""
You are TenderSense AI, a tender and compliance intelligence decision-support assistant.
Answer the user's inquiry based strictly on the provided tender RFP context.
Always cite the specific page number(s) where the fact is mentioned.
If the information is not explicitly found in the context, clearly state that the clause is not present.

User Question: {query}

Tender Document Context:
{context_str}
"""
        system_prompt = "You are a professional government and commercial tender analyst. Answer with precise facts and source page citations."
        answer = llm_client.generate(prompt, system_prompt)
        return {"raw_answer": answer}

    def _node_evidence_validator(self, state: TenderWorkflowState) -> Dict[str, Any]:
        raw_ans = state.get("raw_answer", "")
        passages = [RetrievedPassage(**p) for p in state.get("retrieved_passages", [])]
        
        is_grounded, g_score, citations = EvidenceValidator.validate_answer(raw_ans, passages)
        citations_dicts = [c.model_dump() for c in citations]
        
        return {
            "citations": citations_dicts
        }

    def _node_guardrail(self, state: TenderWorkflowState) -> Dict[str, Any]:
        raw_ans = state.get("raw_answer", "")
        passages = [RetrievedPassage(**p) for p in state.get("retrieved_passages", [])]
        citations = [Citation(**c) for c in state.get("citations", [])]

        guard_res = TenderGuardrail.apply(raw_ans, passages, citations)

        return {
            "guardrail_result": guard_res.model_dump(),
            "final_response": guard_res.sanitized_answer,
            "status": guard_res.status,
            "confidence": guard_res.confidence
        }

    def execute(
        self,
        document_id: str,
        query: str,
        document_title: str = "Tender RFP",
        intent: str | None = None,
        requirements: List[Dict[str, Any]] | None = None,
        profile: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        start_time = time.time()
        initial_state: TenderWorkflowState = {
            "document_id": document_id,
            "document_title": document_title,
            "query": query,
            "intent": intent or "",
            "retrieved_passages": [],
            "requirements": requirements or [],
            "profile": profile,
            "compliance_result": None,
            "raw_answer": "",
            "citations": [],
            "guardrail_result": None,
            "final_response": "",
            "confidence": "HIGH",
            "status": "APPROVED",
            "latency_ms": 0.0
        }

        final_state = self.workflow.invoke(initial_state)
        latency = round((time.time() - start_time) * 1000, 2)
        final_state["latency_ms"] = latency
        return final_state
