from typing import List, Dict, Any

# Curated benchmark questions with ground truth answers, expected source pages, and negative guardrail tests
BENCHMARK_QA_SET: List[Dict[str, Any]] = [
    {
        "id": "q1",
        "question": "What is the minimum annual turnover required for bidders?",
        "expected_answer": "Minimum average annual turnover of ₹15 crore (or INR 15 Cr) over the last three financial years.",
        "expected_page": 2,
        "is_negative_test": False,
        "category": "Financial"
    },
    {
        "id": "q2",
        "question": "How many years of prior experience are required to be eligible?",
        "expected_answer": "At least 5 years of experience in enterprise or government cloud and software solutions.",
        "expected_page": 2,
        "is_negative_test": False,
        "category": "Eligibility"
    },
    {
        "id": "q3",
        "question": "Which ISO quality and security certifications are mandatory?",
        "expected_answer": "ISO 9001 and ISO 27001 certifications are mandatory.",
        "expected_page": 3,
        "is_negative_test": False,
        "category": "Certifications"
    },
    {
        "id": "q4",
        "question": "What is the Earnest Money Deposit (EMD) amount specified in the tender?",
        "expected_answer": "EMD amount is ₹5,00,000 (Rupees Five Lakhs).",
        "expected_page": 2,
        "is_negative_test": False,
        "category": "Financial"
    },
    {
        "id": "q5",
        "question": "What is the Performance Bank Guarantee (PBG) percentage?",
        "expected_answer": "10% of the total contract value.",
        "expected_page": 4,
        "is_negative_test": False,
        "category": "Financial"
    },
    {
        "id": "q6",
        "question": "What is the required uptime SLA percentage for the platform?",
        "expected_answer": "System availability and uptime SLA must be at least 99.9%.",
        "expected_page": 3,
        "is_negative_test": False,
        "category": "Technical"
    },
    {
        "id": "q7",
        "question": "What is the delivery and completion timeline for the project?",
        "expected_answer": "Completion timeline is within 6 months from the date of work order award.",
        "expected_page": 4,
        "is_negative_test": False,
        "category": "Delivery"
    },
    {
        "id": "q8",
        "question": "What is the liquidated damages penalty rate for project delays?",
        "expected_answer": "0.5% per week of delay, capped at a maximum of 10% of total contract value.",
        "expected_page": 4,
        "is_negative_test": False,
        "category": "Delivery"
    },
    {
        "id": "q9",
        "question": "Is CMMI Level 3 certification required or preferred?",
        "expected_answer": "CMMI Level 3 or higher certification is required.",
        "expected_page": 3,
        "is_negative_test": False,
        "category": "Certifications"
    },
    {
        "id": "q10",
        "question": "What statutory tax and company registration documents must be submitted?",
        "expected_answer": "GST Registration certificate, PAN Card, and non-blacklisting affidavit.",
        "expected_page": 2,
        "is_negative_test": False,
        "category": "Documentation"
    },
    # Negative / Guardrail Test Queries (must trigger caution or say not found)
    {
        "id": "q11_neg",
        "question": "Does the bidder need to provide ISO 50001 Energy Management certification?",
        "expected_answer": "No evidence or mention of ISO 50001 in the tender document.",
        "expected_page": None,
        "is_negative_test": True,
        "category": "Guardrail_Negative"
    },
    {
        "id": "q12_neg",
        "question": "What is the penalty for using non-electric vehicles for site visits?",
        "expected_answer": "No clause or penalty found regarding vehicle types in the tender document.",
        "expected_page": None,
        "is_negative_test": True,
        "category": "Guardrail_Negative"
    }
]
