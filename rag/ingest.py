"""
rag/ingest.py
Ingests all PDFs from legal_docs/ → chunks → FAISS vector index.

Run once (or re-run whenever you add/update a PDF):
    python -m rag.ingest
"""
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from app.config import settings


def _get_embeddings(model_name: str):
    """Use langchain-huggingface if installed, else fall back to community."""
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        from langchain_community.embeddings import HuggingFaceEmbeddings  # noqa: F401
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def run() -> None:
    data_dir = settings.LEGAL_DOCS_DIR
    db_dir   = settings.FAISS_DB_DIR

    if not os.path.isdir(data_dir):
        logger.error("❌ Folder '%s' not found. Create it and add your PDFs.", data_dir)
        sys.exit(1)

    pdf_files = [f for f in os.listdir(data_dir) if f.lower().endswith(".pdf")]
    if not pdf_files:
        logger.error("❌ No PDFs found in '%s'.", data_dir)
        sys.exit(1)

    # ── Load ──────────────────────────────────────────────────────────────────
    all_docs = []
    for filename in pdf_files:
        path = os.path.join(data_dir, filename)
        try:
            loader = PyPDFLoader(path)
            pages  = loader.load()
            for page in pages:
                page.metadata["source"] = filename
            all_docs.extend(pages)
            logger.info("  ✓ %s — %d pages", filename, len(pages))
        except Exception as e:
            logger.warning("  ✗ %s — failed: %s", filename, e)

    if not all_docs:
        logger.error("❌ No text extracted from PDFs.")
        sys.exit(1)

    # ── Chunk ─────────────────────────────────────────────────────────────────
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(all_docs)
    logger.info("Created %d chunks from %d pages.", len(chunks), len(all_docs))

    # ── Embed + Save ──────────────────────────────────────────────────────────
    logger.info("Loading embedding model …")
    embeddings = _get_embeddings(settings.EMBED_MODEL)

    logger.info("Building FAISS index …")
    db = FAISS.from_documents(chunks, embeddings)
    os.makedirs(db_dir, exist_ok=True)
    db.save_local(db_dir)

    logger.info("✅ FAISS index saved → %s/", db_dir)
    logger.info("   PDFs: %d | Pages: %d | Chunks: %d", len(pdf_files), len(all_docs), len(chunks))


if __name__ == "__main__":
    run()
