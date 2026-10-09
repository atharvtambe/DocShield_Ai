import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class ParsedPage(BaseModel):
    page_number: int
    text: str
    headings: List[str] = []
    tables: List[str] = []
    metadata: Dict[str, Any] = {}

class ParsedDocument(BaseModel):
    filename: str
    file_type: str
    page_count: int
    pages: List[ParsedPage]
    metadata: Dict[str, Any] = {}

class DocumentParser:
    """
    Page-aware parser for tender RFP documents supporting PDF and DOCX formats.
    Extracts structured pages, headings, tables, and provenance metadata.
    """

    @classmethod
    def parse(cls, file_path: str | Path) -> ParsedDocument:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return cls._parse_pdf(path)
        elif suffix in [".docx", ".doc"]:
            return cls._parse_docx(path)
        elif suffix in [".txt", ".md"]:
            return cls._parse_text(path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}. Supported formats: .pdf, .docx, .txt, .md")

    @classmethod
    def _parse_pdf(cls, path: Path) -> ParsedDocument:
        pages: List[ParsedPage] = []
        doc_meta: Dict[str, Any] = {}

        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(path))
            doc_meta = {
                "title": doc.metadata.get("title", path.stem),
                "author": doc.metadata.get("author", ""),
                "creator": doc.metadata.get("creator", ""),
                "total_pages": len(doc)
            }

            for page_idx in range(len(doc)):
                page = doc[page_idx]
                page_num = page_idx + 1
                text = page.get_text("text") or ""
                
                # Detect headings via font sizes or block analysis
                headings: List[str] = []
                blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
                for b in blocks:
                    block_text = b[4].strip()
                    lines = block_text.split("\n")
                    if lines:
                        first_line = lines[0].strip()
                        # Heading heuristics (uppercase, numbered section like "1.2 Eligibility", or short bold-like lines)
                        if cls._is_heading_candidate(first_line):
                            headings.append(first_line)

                # Extract tables if available in PyMuPDF
                tables_text: List[str] = []
                try:
                    tabs = page.find_tables()
                    if tabs and tabs.tables:
                        for tab in tabs:
                            df_tab = tab.extract()
                            if df_tab:
                                md_table = cls._format_table_markdown(df_tab)
                                tables_text.append(md_table)
                except Exception:
                    pass

                pages.append(
                    ParsedPage(
                        page_number=page_num,
                        text=text.strip(),
                        headings=headings,
                        tables=tables_text,
                        metadata={"dimensions": (page.rect.width, page.rect.height)}
                    )
                )

            doc.close()

        except ImportError:
            # Fallback to pypdf if PyMuPDF not available
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            doc_meta = {"total_pages": len(reader.pages)}
            for idx, p in enumerate(reader.pages):
                txt = p.extract_text() or ""
                pages.append(
                    ParsedPage(
                        page_number=idx + 1,
                        text=txt.strip(),
                        headings=cls._extract_regex_headings(txt),
                        tables=[],
                        metadata={}
                    )
                )

        return ParsedDocument(
            filename=path.name,
            file_type="pdf",
            page_count=len(pages),
            pages=pages,
            metadata=doc_meta
        )

    @classmethod
    def _parse_docx(cls, path: Path) -> ParsedDocument:
        import docx
        doc = docx.Document(str(path))
        pages: List[ParsedPage] = []
        headings: List[str] = []
        current_paragraphs: List[str] = []
        current_tables: List[str] = []
        
        # Word docs do not have native page objects until rendered,
        # so we track sections / logical pages by page breaks or section headings
        page_num = 1
        
        for element in doc.element.body:
            if element.tag.endswith('p'):
                # Paragraph
                for p in doc.paragraphs:
                    if p._p == element:
                        text = p.text.strip()
                        if not text:
                            continue
                        # Check if Heading style or manual page break
                        if "Heading" in p.style.name or cls._is_heading_candidate(text):
                            headings.append(text)
                        
                        # Check for page break XML
                        if 'lastRenderedPageBreak' in p._p.xml or 'w:br w:type="page"' in p._p.xml:
                            if current_paragraphs:
                                pages.append(ParsedPage(
                                    page_number=page_num,
                                    text="\n\n".join(current_paragraphs),
                                    headings=list(headings),
                                    tables=list(current_tables)
                                ))
                                page_num += 1
                                current_paragraphs = []
                                current_tables = []
                                headings = []

                        current_paragraphs.append(text)
                        break
            elif element.tag.endswith('tbl'):
                # Table
                for t in doc.tables:
                    if t._tbl == element:
                        rows_data = []
                        for row in t.rows:
                            rows_data.append([cell.text.strip() for cell in row.cells])
                        if rows_data:
                            current_tables.append(cls._format_table_markdown(rows_data))
                        break

        if current_paragraphs or current_tables:
            pages.append(ParsedPage(
                page_number=page_num,
                text="\n\n".join(current_paragraphs),
                headings=headings,
                tables=current_tables
            ))

        return ParsedDocument(
            filename=path.name,
            file_type="docx",
            page_count=max(len(pages), 1),
            pages=pages,
            metadata={"total_paragraphs": len(doc.paragraphs), "total_tables": len(doc.tables)}
        )

    @classmethod
    def _parse_text(cls, path: Path) -> ParsedDocument:
        content = path.read_text(encoding="utf-8", errors="ignore")
        # Split by page separator markers if present, or split every 2500 characters
        raw_pages = content.split("--- PAGE ")
        pages: List[ParsedPage] = []
        
        if len(raw_pages) > 1:
            for idx, part in enumerate(raw_pages[1:], start=1):
                part_text = part.strip()
                pages.append(ParsedPage(
                    page_number=idx,
                    text=part_text,
                    headings=cls._extract_regex_headings(part_text),
                    tables=[]
                ))
        else:
            # Chunk into simulated pages of ~2000 chars
            lines = content.split("\n")
            cur_lines = []
            cur_len = 0
            page_num = 1
            for line in lines:
                cur_lines.append(line)
                cur_len += len(line)
                if cur_len > 2500:
                    ptxt = "\n".join(cur_lines)
                    pages.append(ParsedPage(
                        page_number=page_num,
                        text=ptxt,
                        headings=cls._extract_regex_headings(ptxt),
                        tables=[]
                    ))
                    page_num += 1
                    cur_lines = []
                    cur_len = 0
            if cur_lines:
                ptxt = "\n".join(cur_lines)
                pages.append(ParsedPage(
                    page_number=page_num,
                    text=ptxt,
                    headings=cls._extract_regex_headings(ptxt),
                    tables=[]
                ))

        return ParsedDocument(
            filename=path.name,
            file_type="text",
            page_count=len(pages),
            pages=pages,
            metadata={}
        )

    @staticmethod
    def _is_heading_candidate(line: str) -> bool:
        line = line.strip()
        if not line or len(line) > 120:
            return False
        # Matches patterns like "1. INTRODUCTION", "SECTION 3: ELIGIBILITY", "ANNEXURE A", etc.
        patterns = [
            r'^(?:SECTION|PART|CLAUSE|ANNEXURE|SCHEDULE|APPENDIX)\s+[A-Z0-9\.\:]+',
            r'^\d+(\.\d+)*\s+[A-Z]',
            r'^[A-Z\s\-\:\/]{4,50}$',
            r'^(?:Eligibility Criteria|Technical Specifications|Commercial Terms|Financial Requirements|Scope of Work)'
        ]
        return any(re.search(pat, line, re.IGNORECASE) for pat in patterns)

    @staticmethod
    def _extract_regex_headings(text: str) -> List[str]:
        headings = []
        for line in text.split("\n")[:10]:
            clean = line.strip()
            if DocumentParser._is_heading_candidate(clean):
                headings.append(clean)
        return headings

    @staticmethod
    def _format_table_markdown(rows: List[List[Any]]) -> str:
        if not rows:
            return ""
        col_count = max(len(r) for r in rows)
        norm_rows = []
        for r in rows:
            row_items = [str(c or "").replace("\n", " ").strip() for c in r]
            while len(row_items) < col_count:
                row_items.append("")
            norm_rows.append(row_items)

        header = norm_rows[0]
        md = ["| " + " | ".join(header) + " |"]
        md.append("| " + " | ".join(["---"] * col_count) + " |")
        for r in norm_rows[1:]:
            md.append("| " + " | ".join(r) + " |")
        return "\n".join(md)
