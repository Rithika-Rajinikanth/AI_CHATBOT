"""
agents/retriever.py
Thin wrapper around FAISS similarity_search.
"""
import logging
from app.config import settings

logger = logging.getLogger(__name__)


def retrieve(query: str, db, k: int = None) -> list:
    """
    Returns the top-k most relevant document chunks for a query.
    Returns [] if db is None (FAISS not yet loaded).
    """
    if db is None:
        logger.warning("retrieve() called but FAISS db is not loaded.")
        return []

    k = k or settings.RETRIEVER_K
    try:
        docs = db.similarity_search(query, k=k)
        logger.debug("retriever: %d chunks for '%s…'", len(docs), query[:40])
        return docs
    except Exception as e:
        logger.error("retriever error: %s", e)
        return []
