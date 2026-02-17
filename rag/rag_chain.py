"""
rag/rag_chain.py
Module-level singletons: FAISS vector store + Ollama local LLM.
Initialised once via init_rag() during FastAPI lifespan startup.

Key design: NOTHING in this file ever raises an exception that
reaches the caller. All failures are logged and set the global
to None — the server stays up and returns 503 for LLM-dependent
routes rather than crashing entirely.
"""
import logging

logger = logging.getLogger(__name__)

db  = None   # FAISS vector store  (None → RAG unavailable)
llm = None   # Ollama LLM instance (None → chat unavailable)


def _load_embeddings(model_name: str):
    """Try langchain-huggingface first, fall back to langchain-community."""
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        logger.info("Using langchain_huggingface.HuggingFaceEmbeddings")
    except ImportError:
        from langchain_community.embeddings import HuggingFaceEmbeddings  # noqa: F401
        logger.info("Using langchain_community.HuggingFaceEmbeddings (consider: pip install langchain-huggingface)")

    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def _load_faiss(db_dir: str, model_name: str):
    """Load FAISS index. Returns db or None."""
    import os
    from langchain_community.vectorstores import FAISS

    if not os.path.isdir(db_dir):
        logger.warning("⚠️  FAISS index not found at '%s'. Run: python -m rag.ingest", db_dir)
        return None

    try:
        embeddings = _load_embeddings(model_name)
        db = FAISS.load_local(db_dir, embeddings, allow_dangerous_deserialization=True)
        logger.info("✅ FAISS index loaded from '%s'.", db_dir)
        return db
    except Exception as e:
        logger.error("❌ FAISS load failed: %s", e)
        return None


def _load_ollama(base_url: str, model: str, temperature: float):
    """
    Connect to Ollama. Returns llm or None.

    OllamaLLM() does NOT make a network call on construction — it's lazy.
    The actual connection happens on the first .invoke() call.
    So construction is always safe; we just need to handle import errors.
    """
    try:
        # langchain-ollama >= 0.1.0 ships OllamaLLM
        from langchain_ollama import OllamaLLM
        llm = OllamaLLM(
            model=model,
            base_url=base_url,
            temperature=temperature,
        )
        logger.info("✅ Ollama LLM configured — model=%s  url=%s", model, base_url)
        logger.info("   (Connection to Ollama is verified on first chat request)")
        return llm
    except ImportError:
        pass

    try:
        # Older builds export ChatOllama instead
        from langchain_ollama import ChatOllama
        llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
        )
        logger.info("✅ ChatOllama configured — model=%s  url=%s", model, base_url)
        return llm
    except ImportError:
        pass

    try:
        # Last resort: langchain_community Ollama wrapper
        from langchain_community.llms import Ollama
        llm = Ollama(
            model=model,
            base_url=base_url,
            temperature=temperature,
        )
        logger.info("✅ Ollama (community) configured — model=%s", model)
        return llm
    except ImportError as e:
        logger.error(
            "❌ No Ollama LLM class found: %s\n"
            "   Run: pip install langchain-ollama", e
        )
        return None
    except Exception as e:
        logger.error("❌ Ollama init error: %s", e)
        return None


def init_rag() -> None:
    """
    Called once during FastAPI lifespan startup.
    Never raises — all failures are logged and stored as None.
    """
    global db, llm

    try:
        from app.config import settings

        db  = _load_faiss(settings.FAISS_DB_DIR, settings.EMBED_MODEL)
        llm = _load_ollama(settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL, settings.OLLAMA_TEMPERATURE)

    except Exception as e:
        # This should never happen, but if it does the server still starts
        logger.error("❌ Unexpected error in init_rag: %s", e, exc_info=True)
        db  = None
        llm = None