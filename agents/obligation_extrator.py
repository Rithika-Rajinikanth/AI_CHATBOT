"""
agents/obligation_extractor.py
Extracts legal obligations (SHALL / MUST / REQUIRED) from document text.
"""
import logging

logger = logging.getLogger(__name__)

_PROMPT = """\
You are a legal analyst. Extract every obligation from the text below.
An obligation uses the words: SHALL, MUST, REQUIRED, OBLIGATED, or WILL.

Rules:
- Return ONLY bullet points starting with "•"
- Include the responsible party in parentheses, e.g. (Farmer), (Company)
- Do NOT add commentary or preamble
- If none found, return: • No obligations found

TEXT:
{text}

OBLIGATIONS:"""


def extract(llm, text: str) -> list:
    """
    Args:
        llm:  Ollama LLM instance
        text: Raw legal text

    Returns:
        List of obligation strings (bullet points)
    """
    if not text.strip():
        return ["No text provided."]

    truncated = text[:6000] + ("…[truncated]" if len(text) > 6000 else "")

    try:
        response = llm.invoke(_PROMPT.format(text=truncated))
        raw = response.content if hasattr(response, "content") else str(response)

        lines = [l.strip() for l in raw.split("\n") if l.strip().startswith("•")]
        return lines if lines else ["No obligations extracted."]
    except Exception as e:
        logger.error("obligation_extractor error: %s", e)
        return [f"Error: {e}"]
