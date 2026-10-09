import time
import re
from typing import List, Dict, Any, Optional
from backend.models import EvaluationRunORM
from backend.graph.workflow import TenderWorkflowManager
from backend.evaluation.benchmark_dataset import BENCHMARK_QA_SET

class TenderEvaluator:
    """
    Automated Evaluation Suite for TenderSense AI:
    Measures Retrieval Recall, Answer Accuracy, Citation Accuracy,
    Hallucination Rate, and Latency according to the Project Blueprint.
    """

    def __init__(self, workflow_manager: TenderWorkflowManager):
        self.workflow_manager = workflow_manager

    def run_evaluation(
        self,
        document_id: str,
        benchmark_set: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        dataset = benchmark_set or BENCHMARK_QA_SET
        total_questions = len(dataset)
        
        recall_hits = 0
        citation_hits = 0
        accuracy_scores: List[float] = []
        hallucination_count = 0
        latencies: List[float] = []
        detailed_results: List[Dict[str, Any]] = []

        for item in dataset:
            q_id = item["id"]
            question = item["question"]
            expected_ans = item["expected_answer"]
            exp_page = item.get("expected_page")
            is_negative = item.get("is_negative_test", False)

            start_t = time.time()
            res = self.workflow_manager.execute(
                document_id=document_id,
                query=question,
                intent="QA_RETRIEVAL"
            )
            lat = (time.time() - start_t) * 1000
            latencies.append(lat)

            generated_ans = res.get("final_response", "")
            citations = res.get("citations", [])
            retrieved = res.get("retrieved_passages", [])
            retrieved_pages = [p.get("page") for p in retrieved]
            cited_pages = [c.get("page") for c in citations]

            # 1. Retrieval Recall
            if exp_page is not None:
                retrieval_success = exp_page in retrieved_pages
                if retrieval_success:
                    recall_hits += 1
            else:
                retrieval_success = True  # Negative query

            # 2. Citation Accuracy
            if exp_page is not None:
                citation_success = exp_page in cited_pages
                if citation_success:
                    citation_hits += 1
            else:
                citation_success = len(citations) == 0 or res.get("status") in ["BLOCKED", "QUALIFIED"]

            # 3. Answer Accuracy (Token Overlap & Semantic Alignment)
            if not is_negative:
                acc_score = self._compute_token_overlap(generated_ans, expected_ans)
                accuracy_scores.append(acc_score)
                # Check hallucination: if confidence high but wrong facts
                is_hallucinated = acc_score < 0.2 and res.get("confidence") == "HIGH"
                if is_hallucinated:
                    hallucination_count += 1
            else:
                # For negative tests: system should state not found, blocked, or qualified
                blocked_or_absent = any(w in generated_ans.lower() for w in [
                    "no relevant clauses", "not found", "no evidence", "does not contain", "cannot be inferred"
                ]) or res.get("status") in ["BLOCKED", "QUALIFIED"]
                acc_score = 1.0 if blocked_or_absent else 0.0
                accuracy_scores.append(acc_score)
                is_hallucinated = not blocked_or_absent
                if is_hallucinated:
                    hallucination_count += 1

            detailed_results.append({
                "id": q_id,
                "question": question,
                "category": item.get("category", "General"),
                "expected_answer": expected_ans,
                "generated_answer": generated_ans,
                "expected_page": exp_page,
                "cited_pages": cited_pages,
                "retrieved_pages": retrieved_pages[:3],
                "retrieval_success": retrieval_success,
                "citation_success": citation_success,
                "accuracy_score": round(acc_score, 2),
                "is_hallucinated": is_hallucinated,
                "latency_ms": round(lat, 1),
                "guardrail_status": res.get("status")
            })

        positive_count = sum(1 for item in dataset if not item.get("is_negative_test"))
        retrieval_recall = round((recall_hits / max(positive_count, 1)) * 100, 1)
        citation_acc = round((citation_hits / max(positive_count, 1)) * 100, 1)
        answer_acc = round((sum(accuracy_scores) / max(len(accuracy_scores), 1)) * 100, 1)
        hallucination_rate = round((hallucination_count / max(total_questions, 1)) * 100, 1)
        avg_latency = round(sum(latencies) / max(len(latencies), 1), 1)

        summary = {
            "total_questions": total_questions,
            "retrieval_recall_pct": retrieval_recall,
            "answer_accuracy_pct": answer_acc,
            "citation_accuracy_pct": citation_acc,
            "hallucination_rate_pct": hallucination_rate,
            "avg_latency_ms": avg_latency,
            "detailed_results": detailed_results
        }
        return summary

    @staticmethod
    def _compute_token_overlap(predicted: str, reference: str) -> float:
        # Extract meaningful alphanumeric tokens
        def tokens(txt: str):
            words = re.findall(r'[a-zA-Z0-9]+', txt.lower())
            stop_words = {"the", "a", "an", "is", "of", "and", "in", "to", "for", "with", "or", "by", "from", "on"}
            return set(w for w in words if w not in stop_words and len(w) > 1)

        pred_toks = tokens(predicted)
        ref_toks = tokens(reference)
        if not ref_toks:
            return 1.0 if not pred_toks else 0.0

        overlap = len(pred_toks & ref_toks)
        # Recall against reference
        ref_coverage = overlap / len(ref_toks)
        return min(1.0, ref_coverage * 1.2)  # Generous scaling for partial matches
