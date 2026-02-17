"""
agents/legal_reasoner.py
Builds a strict RAG prompt and calls the Ollama LLM.
The LLM must answer using ONLY the provided legal document context.
"""
import logging

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a legal assistant for AgriConnect Pro, a smart agricultural platform.\n"
    "Answer ONLY using the context provided below.\n"
    "If the context does not contain enough information, respond:\n"
    "  'I could not find this in the legal documents. "
    "Please contact support@agriconnectpro.in'\n"
    "Do NOT speculate. Be precise and professional."
)


def reason(llm, docs: list, query: str, role_context: str = "") -> str:
    """
    Args:
        llm:          Ollama LLM instance from rag_chain
        docs:         Retrieved Document chunks (FAISS)
        query:        User's question
        role_context: Optional live Firebase data block (IoT / auction)

    Returns:
        Answer string
    """
    if not docs:
        return (
            "No relevant legal documents found for your query. "
            "Contact support@agriconnectpro.in"
        )

    # Build numbered context with source labels
    context_parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "Legal Document")
        context_parts.append(f"[Source {i} — {source}]\n{doc.page_content.strip()}")

    context_block = "\n\n".join(context_parts)

    firebase_block = (
        f"\n\n--- LIVE PLATFORM DATA ---\n{role_context}\n---"
        if role_context else ""
    )

    prompt = (
        f"{_SYSTEM}\n\n"
        f"--- LEGAL DOCUMENT CONTEXT ---\n{context_block}"
        f"{firebase_block}\n\n"
        f"--- QUESTION ---\n{query}\n\n"
        f"--- ANSWER ---"
    )

    try:
        response = llm.invoke(prompt)
        # OllamaLLM returns a plain string; ChatOllama returns an AIMessage
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error("legal_reasoner error: %s", e)
        return f"Error generating response: {e}"
