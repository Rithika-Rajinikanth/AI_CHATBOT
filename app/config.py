"""
app/config.py
Loads every environment variable from .env once at startup.
All other modules import `settings` from here — never os.getenv() directly.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── Firebase ───────────────────────────────────────────────────────────────
    FIREBASE_CREDENTIALS: str = os.getenv("FIREBASE_CREDENTIALS", "serviceAccountKey.json")
    FIREBASE_RTDB_URL:    str = os.getenv("FIREBASE_RTDB_URL", "")

    # ── JWT ────────────────────────────────────────────────────────────────────
    # ONE secret signs all access tokens.
    # ONE refresh secret signs all refresh tokens.
    # The user's role ("farmer" | "dealer" | "user") lives INSIDE the token payload.
    JWT_SECRET:                str = os.getenv("JWT_SECRET", "")
    JWT_REFRESH_SECRET:        str = os.getenv("JWT_REFRESH_SECRET", "")
    JWT_ALGORITHM:             str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_EXPIRE_MINUTES", 30))
    JWT_REFRESH_EXPIRE_DAYS:   int = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", 7))

    # ── Ollama local LLM ───────────────────────────────────────────────────────
    OLLAMA_BASE_URL:    str   = os.getenv("OLLAMA_BASE_URL",    "http://localhost:11434")
    OLLAMA_MODEL:       str   = os.getenv("OLLAMA_MODEL",       "llama3:8b")
    OLLAMA_TEMPERATURE: float = float(os.getenv("OLLAMA_TEMPERATURE", 0.1))

    # ── RAG / FAISS ────────────────────────────────────────────────────────────
    LEGAL_DOCS_DIR: str = "legal_docs"
    FAISS_DB_DIR:   str = "faiss_db"
    EMBED_MODEL:    str = "sentence-transformers/all-MiniLM-L6-v2"
    CHUNK_SIZE:     int = 800
    CHUNK_OVERLAP:  int = 150
    RETRIEVER_K:    int = 5

    # ── Valid roles ────────────────────────────────────────────────────────────
    VALID_ROLES: set = {"user", "farmer", "dealer"}


settings = Settings()
