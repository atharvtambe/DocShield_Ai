import pytest
from pathlib import Path
from backend.ingestion.parser import DocumentParser
from backend.ingestion.chunker import SectionAwareChunker

def test_pdf_parsing_preserves_pages():
    pdf_path = Path("documents/sample_smart_city_tender.pdf")
    assert pdf_path.exists(), "Sample PDF must exist"

    doc = DocumentParser.parse(pdf_path)
    assert doc.page_count == 4
    assert doc.file_type == "pdf"
    assert len(doc.pages) == 4
    assert doc.pages[0].page_number == 1
    assert "SMART CITY" in doc.pages[0].text.upper()
    assert doc.pages[1].page_number == 2
    assert "ELIGIBILITY" in doc.pages[1].text.upper()

def test_docx_parsing():
    docx_path = Path("documents/sample_highway_tender.docx")
    assert docx_path.exists(), "Sample DOCX must exist"

    doc = DocumentParser.parse(docx_path)
    assert doc.page_count >= 1
    assert doc.file_type == "docx"
    assert "HIGHWAY" in doc.pages[0].text.upper()

def test_chunking_preserves_provenance():
    pdf_path = Path("documents/sample_smart_city_tender.pdf")
    parsed_doc = DocumentParser.parse(pdf_path)

    chunker = SectionAwareChunker(chunk_size=400, overlap=50)
    chunks = chunker.chunk_document("test-doc-id", parsed_doc)

    assert len(chunks) > 0
    for c in chunks:
        assert c.chunk_id.startswith("doc_test-doc-id_p")
        assert c.document_id == "test-doc-id"
        assert c.page in [1, 2, 3, 4]
        assert len(c.text) > 0
        assert c.section in ["General Information", "Eligibility", "Technical", "Financial", "Certifications", "Documentation", "Delivery", "Evaluation"]
