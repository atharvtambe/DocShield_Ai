import re
from typing import List, Dict, Any, Optional
from backend.models import ChunkProvenance
from backend.ingestion.parser import ParsedDocument
from backend.config import settings

class SectionAwareChunker:
    """
    Splits parsed document pages into coherent chunks while preserving
    strict provenance: page numbers, current section, heading hierarchy, and chunk IDs.
    """

    KNOWN_SECTIONS = [
        ("Eligibility", [r"eligibility", r"pre-qualification", r"bidder qualifying", r"qualification criteria"]),
        ("Technical", [r"technical specification", r"scope of work", r"functional requirement", r"deliverable", r"technical parameter"]),
        ("Financial", [r"turnover", r"financial requirement", r"annual turnover", r"earnest money", r"emd", r"bid security", r"financial bid"]),
        ("Certifications", [r"iso\s*\d+", r"certification", r"quality standard", r"cmmi", r"compliance standard"]),
        ("Documentation", [r"document required", r"annexure", r"checklist", r"bid submission", r"format of", r"undertaking"]),
        ("Delivery", [r"delivery schedule", r"timeline", r"completion period", r"milestone", r"sla", r"penalty", r"liquidated damages"]),
        ("Evaluation", [r"evaluation criteria", r"marking system", r"qcbs", r"selection process", r"scoring matrix"])
    ]

    def __init__(self, chunk_size: int = settings.CHUNK_SIZE, overlap: int = settings.CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_document(self, doc_id: str, parsed_doc: ParsedDocument) -> List[ChunkProvenance]:
        chunks: List[ChunkProvenance] = []
        current_section = "General Information"
        current_heading = "General"
        chunk_idx = 0

        for page in parsed_doc.pages:
            # Check if any heading on this page introduces a new section
            for h in page.headings:
                detected_section = self._classify_section(h)
                if detected_section:
                    current_section = detected_section
                current_heading = h

            page_text = page.text
            # Append markdown tables if any
            if page.tables:
                tables_block = "\n\n".join(page.tables)
                page_text = f"{page_text}\n\n[TABLES DETECTED ON PAGE {page.page_number}]\n{tables_block}"

            page_chunks_text = self._split_text(page_text)
            
            for p_chunk in page_chunks_text:
                if not p_chunk.strip():
                    continue

                # Context-aware heading/section re-check for this snippet
                snip_sec = self._classify_section(p_chunk[:200]) or current_section

                chunk_id = f"doc_{doc_id}_p{page.page_number}_c{chunk_idx}"
                provenance = ChunkProvenance(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    text=p_chunk.strip(),
                    page=page.page_number,
                    section=snip_sec,
                    heading=current_heading,
                    metadata={
                        "char_count": len(p_chunk),
                        "has_table": "[TABLES DETECTED" in p_chunk,
                        "file_name": parsed_doc.filename
                    }
                )
                chunks.append(provenance)
                chunk_idx += 1

        return chunks

    def _classify_section(self, text: str) -> Optional[str]:
        for sec_name, patterns in self.KNOWN_SECTIONS:
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    return sec_name
        return None

    def _split_text(self, text: str) -> List[str]:
        # Split by paragraphs / double newlines first
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
        chunks: List[str] = []
        current_buffer = ""

        for para in paragraphs:
            if len(para) > self.chunk_size:
                # If paragraph itself is larger than chunk_size, split by sentences
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sent in sentences:
                    if len(current_buffer) + len(sent) + 1 <= self.chunk_size:
                        current_buffer += (" " if current_buffer else "") + sent
                    else:
                        if current_buffer:
                            chunks.append(current_buffer)
                            # Overlap buffer with tail
                            overlap_len = min(self.overlap, len(current_buffer))
                            current_buffer = current_buffer[-overlap_len:] + " " + sent
                        else:
                            chunks.append(sent)
                            current_buffer = ""
            else:
                if len(current_buffer) + len(para) + 2 <= self.chunk_size:
                    current_buffer += ("\n\n" if current_buffer else "") + para
                else:
                    if current_buffer:
                        chunks.append(current_buffer)
                        overlap_len = min(self.overlap, len(current_buffer))
                        current_buffer = current_buffer[-overlap_len:] + "\n\n" + para
                    else:
                        current_buffer = para

        if current_buffer.strip():
            chunks.append(current_buffer.strip())

        return chunks if chunks else [text]
