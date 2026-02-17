"""
agents/compliance_checker.py
Checks whether the LLM answer is grounded in the retrieved documents.

Grounding levels:
  ✅ Grounded   — strong token overlap, no speculative language
  ⚠️ Partial    — some overlap or minor hedging detected
  ❌ Not Grounded — low overlap, likely hallucinated
"""
import re
import logging

logger = logging.getLogger(__name__)

_HEDGE_WORDS = {
    "assume", "likely", "generally", "probably", "perhaps",
    "maybe", "i think", "i believe", "could be", "might be",
    "in most cases", "typically",
}


def _overlap(answer: str, context: str) -> float:
    a_tokens = set(re.findall(r"\b\w{4,}\b", answer.lower()))
    c_tokens = set(re.findall(r"\b\w{4,}\b", context.lower()))
    if not a_tokens:
        return 0.0
    return len(a_tokens & c_tokens) / len(a_tokens)


def check(answer: str, docs: list) -> dict:
    """
    Returns:
        {"status": str, "score": float, "detail": str}
    """
    if not answer or not docs:
        return {"status": "❌ Not Grounded", "score": 0.0, "detail": "Empty answer or no source docs."}

    context    = " ".join(d.page_content for d in docs)
    hedges     = [w for w in _HEDGE_WORDS if w in answer.lower()]
    score      = _overlap(answer, context)

    if score >= 0.40 and not hedges:
        status = "✅ Grounded"
        detail = f"Token overlap: {score:.0%}. No speculative language."
    elif score >= 0.20 or not hedges:
        status = "⚠️ Partial"
        detail = f"Token overlap: {score:.0%}. Hedges found: {', '.join(hedges) or 'none'}."
    else:
        status = "❌ Not Grounded"
        detail = f"Token overlap: {score:.0%}. Answer may not be grounded in sources."

    return {"status": status, "score": round(score, 3), "detail": detail}
