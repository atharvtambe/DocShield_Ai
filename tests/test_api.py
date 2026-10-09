import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "TenderSense AI" in data["app"]

def test_load_sample_tender_and_full_lifecycle():
    # 1. Load sample tender
    resp = client.post("/api/tenders/sample/load?sample_type=smart_city")
    assert resp.status_code == 200
    tender_data = resp.json()
    doc_id = tender_data["id"]
    assert doc_id is not None
    assert tender_data["pages"] == 4

    # 2. List tenders
    list_resp = client.get("/api/tenders")
    assert list_resp.status_code == 200
    tenders = list_resp.json()
    assert len(tenders) >= 1

    # 3. Get tender detail
    det_resp = client.get(f"/api/tenders/{doc_id}")
    assert det_resp.status_code == 200
    assert det_resp.json()["id"] == doc_id

    # 4. Get extracted requirements
    req_resp = client.get(f"/api/tenders/{doc_id}/requirements")
    assert req_resp.status_code == 200
    req_data = req_resp.json()
    assert req_data["total"] >= 3

    # 5. Evaluate compliance
    comp_resp = client.post(f"/api/tenders/{doc_id}/compliance")
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    assert comp_data["readiness_score"] >= 0
    assert comp_data["overall_status"] in ["QUALIFIED", "PARTIAL", "DISQUALIFIED"]

    # 6. Test Evidence-backed AI Chat
    chat_resp = client.post(f"/api/tenders/{doc_id}/chat", json={
        "document_id": doc_id,
        "question": "What is the minimum annual turnover required?",
        "include_citations": True
    })
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert len(chat_data["answer"]) > 0
    assert chat_data["confidence"] in ["HIGH", "MEDIUM", "LOW"]
    assert len(chat_data["citations"]) > 0

    # 7. Get Executive Report
    rep_resp = client.get(f"/api/tenders/{doc_id}/report?format=markdown")
    assert rep_resp.status_code == 200
    assert "Executive Bid-Readiness Report" in rep_resp.text

    # 8. Run Evaluation Suite
    eval_resp = client.post(f"/api/evaluation/run?tender_id={doc_id}")
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["total_questions"] >= 10
    assert eval_data["retrieval_recall_pct"] >= 50.0
