import pytest
from backend.models import RequirementItem, CompanyProfileSchema
from backend.agents.compliance_agent import ComplianceAgent

def test_compliance_evaluation_qualified():
    agent = ComplianceAgent()
    reqs = [
        RequirementItem(category="Eligibility", description="Minimum 5 years of experience", value="5 years", mandatory=True, page=2),
        RequirementItem(category="Financial", description="Annual turnover of 15 crores", value="15 crores", mandatory=True, page=2),
        RequirementItem(category="Certifications", description="ISO 9001 certification", value="ISO 9001", mandatory=True, page=3)
    ]

    profile = CompanyProfileSchema(
        company_name="Apex Global Tech",
        turnover_cr=25.0,  # Exceeds 15 Cr
        experience_years=8.0,  # Exceeds 5 yrs
        certifications=["ISO 9001", "ISO 27001"],
        technical_capabilities=["Cloud", "Analytics"]
    )

    result = agent.evaluate_compliance("doc-1", "Test Tender", reqs, profile)
    assert result.overall_status == "QUALIFIED"
    assert result.readiness_score == 100.0
    assert result.satisfied_count == 3
    assert result.missing_count == 0

def test_compliance_evaluation_disqualified():
    agent = ComplianceAgent()
    reqs = [
        RequirementItem(category="Eligibility", description="Minimum 10 years experience", value="10 years", mandatory=True, page=2),
        RequirementItem(category="Certifications", description="ISO 14001 certification", value="ISO 14001", mandatory=True, page=3)
    ]

    profile = CompanyProfileSchema(
        company_name="Startup Ltd",
        turnover_cr=2.0,
        experience_years=2.0,  # Below 10 yrs
        certifications=["ISO 9001"],  # Missing ISO 14001
        technical_capabilities=[]
    )

    result = agent.evaluate_compliance("doc-2", "Test Tender", reqs, profile)
    assert result.overall_status == "DISQUALIFIED"
    assert result.missing_count >= 1
