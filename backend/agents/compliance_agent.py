import re
from typing import List, Dict, Any
from backend.models import RequirementItem, CompanyProfileSchema, ComplianceItem, ComplianceSummaryResponse

class ComplianceAgent:
    """
    Evaluates tender requirements against a company's profile.
    Produces granular requirement status (SATISFIED, MISSING, RISKY, CLARIFICATION_NEEDED)
    and an overall bid-readiness score and recommendation.
    """

    def evaluate_compliance(
        self,
        document_id: str,
        document_title: str,
        requirements: List[RequirementItem],
        profile: CompanyProfileSchema
    ) -> ComplianceSummaryResponse:
        items: List[ComplianceItem] = []

        satisfied_count = 0
        missing_count = 0
        risky_count = 0
        clarification_count = 0

        for req in requirements:
            status, reason, co_val, req_val = self._evaluate_single_requirement(req, profile)
            
            if status == "SATISFIED":
                satisfied_count += 1
            elif status == "MISSING":
                missing_count += 1
            elif status == "RISKY":
                risky_count += 1
            else:
                clarification_count += 1

            items.append(
                ComplianceItem(
                    requirement_id=req.id,
                    category=req.category,
                    requirement_text=req.description,
                    mandatory=req.mandatory,
                    page=req.page,
                    company_value=co_val,
                    required_value=req_val,
                    status=status,
                    reason=reason,
                    evidence_snippet=req.raw_quote or ""
                )
            )

        total_reqs = len(requirements)
        if total_reqs == 0:
            readiness_score = 0.0
            overall_status = "PARTIAL"
            summary_text = "No explicit requirements extracted to evaluate."
        else:
            # Score formula: 100 * (satisfied + 0.5 * risky) / total
            score_val = (satisfied_count * 1.0 + risky_count * 0.4) / total_reqs * 100.0
            readiness_score = round(min(100.0, max(0.0, score_val)), 1)

            # Determine qualification status
            mandatory_missing = any(it.mandatory and it.status == "MISSING" for it in items)
            if mandatory_missing:
                overall_status = "DISQUALIFIED"
                summary_text = (
                    f"Profile does not meet {missing_count} mandatory criteria. "
                    "Recommend addressing missing qualifications or partnering with a consortium before bidding."
                )
            elif readiness_score >= 80.0:
                overall_status = "QUALIFIED"
                summary_text = (
                    f"Strong bid readiness ({readiness_score}%). All critical mandatory conditions met. "
                    "Proceed with formal bid submission preparation."
                )
            else:
                overall_status = "PARTIAL"
                summary_text = (
                    f"Partial readiness ({readiness_score}%). Some non-mandatory or clarification items pending. "
                    "Review highlighted risks before final submission."
                )

        return ComplianceSummaryResponse(
            document_id=document_id,
            document_title=document_title,
            overall_status=overall_status,
            readiness_score=readiness_score,
            total_requirements=total_reqs,
            satisfied_count=satisfied_count,
            missing_count=missing_count,
            risky_count=risky_count,
            clarification_count=clarification_count,
            summary_text=summary_text,
            items=items
        )

    def _evaluate_single_requirement(
        self,
        req: RequirementItem,
        profile: CompanyProfileSchema
    ) -> tuple[str, str, str, str]:
        text_lower = (req.description + " " + req.value).lower()

        # 1. Experience Check
        if "experience" in text_lower or req.category == "Eligibility":
            exp_match = re.search(r'(\d+)\s*(?:years?|yrs?)', text_lower)
            if exp_match:
                req_years = float(exp_match.group(1))
                co_years = profile.experience_years
                req_val_str = f"≥ {req_years} years"
                co_val_str = f"{co_years} years"
                if co_years >= req_years:
                    return "SATISFIED", f"Company experience of {co_years} yrs meets or exceeds {req_years} yrs.", co_val_str, req_val_str
                elif co_years >= req_years - 1:
                    return "RISKY", f"Company experience of {co_years} yrs is slightly below requirement ({req_years} yrs).", co_val_str, req_val_str
                else:
                    return "MISSING", f"Company experience ({co_years} yrs) fails requirement ({req_years} yrs).", co_val_str, req_val_str

        # 2. Turnover Check
        if "turnover" in text_lower or (req.category == "Financial" and any(u in text_lower for u in ["crore", "cr", "lakh"])):
            to_match = re.search(r'(\d+(?:\.\d+)?)\s*(crores?|cr|lakhs?)', text_lower)
            if to_match:
                amount = float(to_match.group(1))
                unit = to_match.group(2)
                # Normalize to crores
                req_cr = amount if "lakh" not in unit else amount / 100.0
                co_cr = profile.turnover_cr
                req_val_str = f"≥ ₹{req_cr} Cr"
                co_val_str = f"₹{co_cr} Cr"
                if co_cr >= req_cr:
                    return "SATISFIED", f"Annual turnover (₹{co_cr} Cr) satisfies requirement (₹{req_cr} Cr).", co_val_str, req_val_str
                elif co_cr >= req_cr * 0.85:
                    return "RISKY", f"Turnover of ₹{co_cr} Cr is borderline against required ₹{req_cr} Cr.", co_val_str, req_val_str
                else:
                    return "MISSING", f"Annual turnover of ₹{co_cr} Cr is insufficient (required ₹{req_cr} Cr).", co_val_str, req_val_str

        # 3. Certifications Check (ISO, CMMI, etc.)
        if req.category == "Certifications" or any(cert_kw in text_lower for cert_kw in ["iso", "cmmi", "soc", "bis"]):
            cert_name = req.value if req.value else req.description
            req_val_str = cert_name
            # Check if any profile cert matches
            matched = False
            for c in profile.certifications:
                clean_c = re.sub(r'[^a-zA-Z0-9]', '', c.lower())
                clean_req = re.sub(r'[^a-zA-Z0-9]', '', cert_name.lower())
                if clean_c in clean_req or clean_req in clean_c:
                    matched = True
                    break

            if matched:
                return "SATISFIED", f"Company possesses required certification: {cert_name}", "Certified", req_val_str
            else:
                return "MISSING", f"Company profile lacks certificate: {cert_name}", "Not Held", req_val_str

        # 4. Documentation Check
        if req.category == "Documentation":
            req_val_str = req.value or "Submission Required"
            # Default to clarification/check needed for statutory undertakings
            return "CLARIFICATION_NEEDED", "Statutory document submission required prior to bid envelope closing.", "Pending Verification", req_val_str

        # 5. Technical Capabilities
        if req.category == "Technical":
            req_val_str = req.value or req.description[:30]
            # Match capabilities
            t_words = set(re.findall(r'[a-zA-Z]{4,}', text_lower))
            caps_words = set(re.findall(r'[a-zA-Z]{4,}', " ".join(profile.technical_capabilities).lower()))
            overlap = t_words & caps_words
            if overlap:
                return "SATISFIED", f"Company profile supports technical capabilities: {', '.join(list(overlap)[:3])}", "Capable", req_val_str
            else:
                return "RISKY", "Technical capability alignment needs verification by solution architect.", "Review Required", req_val_str

        # Default fallback
        return "CLARIFICATION_NEEDED", "Verify clause with legal and delivery team.", "Unverified", req.value or "Standard Clause"
