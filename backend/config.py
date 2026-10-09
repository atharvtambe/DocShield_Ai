import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "TenderSense AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Storage paths
    BASE_DIR: Path = BASE_DIR
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"
    DOCUMENTS_DIR: Path = BASE_DIR / "documents"
    CHROMA_PERSIST_DIR: Path = BASE_DIR / "data" / "chroma_db"
    SQLITE_DB_PATH: Path = BASE_DIR / "data" / "tendersense.db"
    
    # LLM Settings
    LLM_PROVIDER: str = "auto"  # "gemini", "openai", "auto", "mock"
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Retrieval Settings
    HYBRID_ALPHA: float = 0.5  # 0.5 balances vector and BM25 equally
    TOP_K_RETRIEVAL: int = 5
    CHUNK_SIZE: int = 600
    CHUNK_OVERLAP: int = 100
    
    # Guardrail Thresholds
    MIN_CONFIDENCE_THRESHOLD: float = 0.35
    REQUIRE_EVIDENCE: bool = True
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

settings = Settings()

# Ensure critical directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
settings.CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
