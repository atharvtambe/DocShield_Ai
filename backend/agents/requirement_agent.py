import re
import uuid
from typing import List, Dict, Any, Optional
from backend.models import ChunkProvenance, RequirementItem
from backend.agents.llm_client import llm_client

class RequirementAgent:
    """
    Agent responsible for extracting and normalizing structured tender requirements
    from document chunks, preserving category, mandatory status, values, and page provenance.
    """

    CATEGORIES = [
        "Eligibility",
        "Technical",
        "Financial",
        "Certifications",
        "Documentation",
        "Delivery",
        "Evaluation"
    ]

    def extract_from_chunks(self, document_id: str, chunks: List[ChunkProvenance]) -> List[RequirementItem]:
        extracted: List[RequirementItem] = []

        if llm_client.is_cloud_enabled():
            # Cloud LLM structured batch extraction
            extracted = self._extract_with_llm(document_id, chunks)
            if extracted:
                return extracted

        # Robust deterministic extraction (works offline and acts as high-precision baseline)
        return self._extract_deterministic(document_id, chunks)

    def _extract_with_llm(self, document_id: str, chunks: List[ChunkProvenance]) -> List[RequirementItem]:
        # Sample chunks covering various sections
        selected_chunks = chunks[:25]
        context_blocks = []
        for c in selected_chunks:
            context_blocks.append(f"[Chunk ID: {c.chunk_id}] [Page: {c.page}] [Section: {c.section}]\n{c.text}")

        prompt = f"""
You are an expert procurement and tender analyst. Analyze the following tender RFP text and extract all explicit requirements.
Categories must be one of: Eligibility, Technical, Financial, Certifications, Documentation, Delivery, Evaluation.

Format the response as a valid JSON array of objects with the exact schema:
[
  {{
    "category": "Eligibility",
    "description": "Minimum prior experience in similar cloud deployments",
    "value": "5 years",
    "mandatory": true,
    "page": 2,
    "evidence_chunk_ids": ["doc_xxx_p2_c1"],
    "confidence": "high",
    "raw_quote": "The bidder must have at least 5 years of experience..."
  }}
]

Tender Text Passages:
{chr(10).join(context_blocks[:15])}
"""
        system_prompt = "You are an automated contract and procurement compliance AI. Return only valid JSON."
        result = llm_client.extract_json(prompt, system_prompt)

        items: List[RequirementItem] = []
        if isinstance(result, list):
            for obj in result:
                if isinstance(obj, dict) and "description" in obj:
                    cat = obj.get("category", "Eligibility")
                    if cat not in self.CATEGORIES:
                        cat = "Eligibility"
                    items.append(
                        RequirementItem(
                            id=str(uuid.uuid4()),
                            category=cat,
                            description=obj.get("description", ""),
                            value=str(obj.get("value", "")),
                            mandatory=bool(obj.get("mandatory", True)),
                            page=int(obj.get("page", 1)),
                            evidence_chunk_ids=obj.get("evidence_chunk_ids", []),
                            confidence=str(obj.get("confidence", "high")),
                            raw_quote=obj.get("raw_quote")
                        )
                    )
        return items

    def _extract_deterministic(self, document_id: str, chunks: List[ChunkProvenance]) -> List[RequirementItem]:
        """
        High-precision pattern matcher for procurement tenders.
        Detects financial limits, years of experience, ISO certifications, EMD/PBG, documentation, and SLAs.
        """
        items: List[RequirementItem] = []
        seen_keys = set()

        # Regular expression patterns for common tender clauses
        patterns = [
            # 1. Experience
            (
                "Eligibility",
                r'(?:minimum|at least|shall have|must have)\s+(\d+)\s*(?:\+)?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|proven track record|in the field)',
                lambda m, c: (
                    f"Minimum {m.group(1)} years of experience in relevant domain",
                    f"{m.group(1)} years",
                    True
                )
            ),
            # 2. Turnover
            (
                "Financial",
                r'(?:annual\s+turnover|average\s+turnover|turnover\s+of)\s*(?:of|not less than|shall be|at least)?\s*(?:(?:inr|rs\.?|₹)\s*)?(\d+(?:\.\d+)?)\s*(crores?|cr|lakhs?|million)',
                lambda m, c: (
                    f"Minimum average annual turnover of {m.group(1)} {m.group(2)}",
                    f"{m.group(1)} {m.group(2)}",
                    True
                )
            ),
            # 3. ISO / Standards Certifications
            (
                "Certifications",
                r'\b(ISO\s*\d{4,5}(?::\d{4})?|CMMI(?:\s*Level\s*\d)?|SOC\s*2|BIS|CE\s*Mark|ITIL)\b',
                lambda m, c: (
                    f"Mandatory certification: {m.group(1)}",
                    m.group(1).strip(),
                    True
                )
            ),
            # 4. EMD / Bid Security
            (
                "Financial",
                r'(?:EMD|Earnest\s+Money\s+Deposit|Bid\s+Security)\s*(?:of|amounting to|is)?\s*(?:(?:inr|rs\.?|₹)\s*)?(\d[\d,]*\s*(?:lakhs?|crores?|cr|thousand)?)',
                lambda m, c: (
                    f"Earnest Money Deposit (EMD) of {m.group(1)}",
                    m.group(1).strip(),
                    True
                )
            ),
            # 5. Performance Bank Guarantee (PBG)
            (
                "Financial",
                r'(?:PBG|Performance\s+Bank\s+Guarantee|Performance\s+Security)\s*(?:of|is)?\s*(\d+%\s*(?:of\s+(?:contract|bid)\s+value)?)',
                lambda m, c: (
                    f"Performance Bank Guarantee (PBG) of {m.group(1)}",
                    m.group(1).strip(),
                    True
                )
            ),
            # 6. Delivery / Timeline
            (
                "Delivery",
                r'(?:completion|delivery|implementation)\s+(?:period|timeline|schedule)\s*(?:shall be|is|within)\s*(\d+\s*(?:months?|weeks?|days?))',
                lambda m, c: (
                    f"Project delivery and completion timeline within {m.group(1)}",
                    m.group(1).strip(),
                    True
                )
            ),
            # 7. SLA / Uptime
            (
                "Technical",
                r'(?:uptime|availability)\s*(?:sla|requirement|of)?\s*(?:shall be|at least|minimum)?\s*(\d{2}(?:\.\d+)?%)',
                lambda m, c: (
                    f"System availability and uptime SLA of {m.group(1)}",
                    m.group(1).strip(),
                    True
                )
            ),
            # 8. Documentation (GST, PAN, Non-blacklisting)
            (
                "Documentation",
                r'\b(GST\s*Registration|PAN\s*Card|Non-blacklisting\s*(?:undertaking|affidavit)|Audited\s*Balance\s*Sheets?|Power\s*of\s*Attorney)\b',
                lambda m, c: (
                    f"Submission of {m.group(1)}",
                    "Required",
                    True
                )
            ),
            # 9. Liquidated Damages / Penalty
            (
                "Delivery",
                r'(?:liquidated\s+damages|penalty)\s*(?:of|shall be)?\s*(\d+(?:\.\d+)?%\s*(?:per\s+(?:week|month))?)',
                lambda m, c: (
                    f"Liquidated damages / penalty clause: {m.group(1)}",
                    m.group(1).strip(),
                    False
                )
            )
        ]

        for chunk in chunks:
            text = chunk.text
            for category, regex_pat, formatter in patterns:
                for match in re.finditer(regex_pat, text, re.IGNORECASE):
                    desc, val, mandatory = formatter(match, chunk)
                    key = f"{category}:{val.lower()}:{chunk.page}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        
                        # Snippet for raw quote
                        start = max(0, match.start() - 40)
                        end = min(len(text), match.end() + 60)
                        raw_quote = text[start:end].strip()

                        items.append(
                            RequirementItem(
                                id=str(uuid.uuid4()),
                                category=category,
                                description=desc,
                                value=val,
                                mandatory=mandatory,
                                page=chunk.page,
                                evidence_chunk_ids=[chunk.chunk_id],
                                confidence="high",
                                raw_quote=f"...{raw_quote}..."
                            )
                        )

        # If few items found, parse section-specific lines
        if len(items) < 3:
            for chunk in chunks:
                if chunk.section in ["Eligibility", "Technical", "Certifications"]:
                    lines = [ln.strip() for ln in chunk.text.split("\n") if len(ln.strip()) > 20]
                    for ln in lines[:2]:
                        k = f"{chunk.section}:{ln[:30]}"
                        if k not in seen_keys:
                            seen_keys.add(k)
                            items.append(
                                RequirementItem(
                                    id=str(uuid.uuid4()),
                                    category=chunk.section if chunk.section in self.CATEGORIES else "Eligibility",
                                    description=ln[:120],
                                    value="Documented in RFP",
                                    mandatory=True,
                                    page=chunk.page,
                                    evidence_chunk_ids=[chunk.chunk_id],
                                    confidence="medium",
                                    raw_quote=ln
                                )
                            )

        return items
