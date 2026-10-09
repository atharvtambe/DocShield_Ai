from datetime import datetime, timezone
from typing import Dict, Any, List
from backend.models import ComplianceSummaryResponse, RequirementItem, CompanyProfileSchema

class ReportGenerator:
    """
    Generates high-impact executive bid-readiness and compliance intelligence reports.
    Outputs markdown, structured JSON, and printer-friendly HTML.
    """

    @classmethod
    def generate_markdown(
        cls,
        document_title: str,
        compliance: ComplianceSummaryResponse,
        profile: CompanyProfileSchema
    ) -> str:
        now_str = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")

        verdict_badge = {
            "QUALIFIED": "🟢 RECOMMENDED TO BID (STRONG MATCH)",
            "PARTIAL": "🟡 CONDITIONAL BID (REVIEW GAPS)",
            "DISQUALIFIED": "🔴 HIGH RISK / NOT RECOMMENDED (DISQUALIFIED)"
        }.get(compliance.overall_status, "🟡 UNDER EVALUATION")

        md_lines = [
            f"# 📄 TenderSense AI — Executive Bid-Readiness Report",
            f"**Tender Document**: {document_title}  ",
            f"**Evaluating Company**: {profile.company_name}  ",
            f"**Generated Date**: {now_str}  ",
            f"**Readiness Score**: **{compliance.readiness_score}/100** ({verdict_badge})  ",
            "",
            "---",
            "",
            "## 1. Executive Summary & Bid Recommendation",
            f"> {compliance.summary_text}",
            "",
            f"The AI Compliance Engine evaluated **{compliance.total_requirements}** extracted clauses against {profile.company_name}'s capabilities profile:",
            f"- **Satisfied Requirements**: {compliance.satisfied_count} ({round(compliance.satisfied_count/max(compliance.total_requirements, 1)*100, 1)}%)",
            f"- **Missing / Failed Mandatory Criteria**: {compliance.missing_count}",
            f"- **Risky / Borderline Criteria**: {compliance.risky_count}",
            f"- **Clarification / Documentation Actions Needed**: {compliance.clarification_count}",
            "",
            "---",
            "",
            "## 2. Granular Compliance Matrix",
            "| Category | Requirement | Required Value | Company Capability | Status | Source Page |",
            "|---|---|---|---|---|---|"
        ]

        for item in compliance.items:
            status_emoji = {
                "SATISFIED": "✅ Passed",
                "MISSING": "❌ Failed",
                "RISKY": "⚠️ Borderline",
                "CLARIFICATION_NEEDED": "ℹ️ Clarification"
            }.get(item.status, item.status)

            req_txt = item.requirement_text.replace("|", "/")
            md_lines.append(
                f"| **{item.category}** | {req_txt} | `{item.required_value}` | `{item.company_value}` | **{status_emoji}** | Page {item.page} |"
            )

        md_lines.extend([
            "",
            "---",
            "",
            "## 3. Disqualification Hazards & Critical Gap Analysis"
        ])

        missing_items = [it for it in compliance.items if it.status == "MISSING"]
        if missing_items:
            for it in missing_items:
                md_lines.append(f"- 🔴 **[{it.category}] {it.requirement_text}** (Page {it.page})")
                md_lines.append(f"  - **Required**: {it.required_value} | **Company**: {it.company_value}")
                md_lines.append(f"  - **Impact**: {it.reason}")
        else:
            md_lines.append("✅ No outright disqualification conditions identified among evaluated clauses.")

        md_lines.extend([
            "",
            "---",
            "",
            "## 4. Strategic Next Actions & Pre-Bid Action Items",
            "1. **Pre-Bid Clarification Letters**: If borderline criteria exist, submit formal queries during the pre-bid conference.",
            "2. **Documentation Readiness**: Verify and notarize all statutory certificates (GST, PAN, Audited Balance Sheets) 72 hours before envelope deadline.",
            "3. **Consortium Evaluation**: If mandatory experience or financial limits are missing, explore forming a Joint Venture / Consortium with an eligible partner.",
            "4. **Human Review**: In line with TenderSense AI design principles, final submission must undergo independent legal and contract sign-off."
        ])

        return "\n".join(md_lines)

    @classmethod
    def generate_html(
        cls,
        document_title: str,
        compliance: ComplianceSummaryResponse,
        profile: CompanyProfileSchema
    ) -> str:
        md = cls.generate_markdown(document_title, compliance, profile)
        # Convert markdown text into styled printable HTML
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>TenderSense AI Report - {document_title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1e293b; max-width: 900px; margin: 40px auto; padding: 20px; }}
    h1 {{ color: #0f172a; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; }}
    h2 {{ color: #1e40af; margin-top: 28px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 10px; text-align: left; }}
    th {{ background-color: #f1f5f9; font-weight: 600; }}
    tr:nth-child(even) {{ background-color: #f8fafc; }}
    blockquote {{ background: #eff6ff; border-left: 4px solid #3b82f6; margin: 16px 0; padding: 12px 16px; border-radius: 4px; }}
    .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 13px; }}
    .print-btn {{ background: #2563eb; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; float: right; }}
    @media print {{ .print-btn {{ display: none; }} body {{ margin: 0; padding: 0; }} }}
  </style>
</head>
<body>
  <button class="print-btn" onclick="window.print()">🖨️ Print / Save as PDF</button>
  <pre style="white-space: pre-wrap; font-family: inherit;">{md}</pre>
</body>
</html>"""
        return html
