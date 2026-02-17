"""
agents/user_agent.py
General User AI Agent — marketplace info + policy/legal Q&A only.
No access to IoT data (farmers only) or bid data (dealers only).
"""
import logging

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are a helpful assistant for AgriConnect Pro, speaking with a GENERAL USER.

Your job:
1. Help the user browse and understand the marketplace (listings, products, prices).
2. Explain platform features: IoT monitoring, auction system, analytics.
3. Answer questions about Privacy Policy and Terms of Service using ONLY legal documents provided.
4. Guide users through account setup and role selection.

Restrictions:
- Do NOT share IoT sensor data (farmers only).
- Do NOT share bid amounts or bidding strategy (dealers only).
- Do NOT speculate on prices or market trends.

Tone: Welcoming, clear, helpful."""


def _fmt_marketplace(data: dict) -> str:
    listings = (data or {}).get("all_listings", [])
    if not listings:
        return "No marketplace listings available."

    lines = ["🛒 AVAILABLE MARKETPLACE LISTINGS:"]
    for item in listings[:8]:
        lines.append(
            f"  • {item.get('name','—')} | ₹{item.get('price','?')} | "
            f"Category: {item.get('category','?')} | "
            f"Seller: {item.get('seller_type','?')}"
        )
    return "\n".join(lines)


def user_response(query: str, llm=None, docs: list = None, firebase_data: dict = None) -> dict:
    marketplace_str = _fmt_marketplace(firebase_data)

    if llm is None:
        return {
            "role": "user",
            "answer": f"ℹ️ General Info:\n\n{marketplace_str}\n\nQuery: {query}",
            "sources": [],
        }

    legal_ctx = ""
    sources   = []
    if docs:
        parts = []
        for i, doc in enumerate(docs, 1):
            src = doc.metadata.get("source", "Legal Doc")
            parts.append(f"[Source {i} — {src}]\n{doc.page_content.strip()}")
            sources.append(src)
        legal_ctx = "\n\n".join(parts)

    prompt = (
        f"{_SYSTEM}\n\n"
        f"--- MARKETPLACE DATA ---\n{marketplace_str}\n\n"
        f"--- LEGAL DOCUMENT CONTEXT ---\n"
        f"{legal_ctx if legal_ctx else 'No legal documents retrieved.'}\n\n"
        f"--- USER QUESTION ---\n{query}\n\n"
        f"--- YOUR RESPONSE ---"
    )

    try:
        response = llm.invoke(prompt)
        answer   = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error("user_agent error: %s", e)
        answer = f"Error: {e}"

    return {
        "role":    "user",
        "answer":  answer,
        "sources": list(set(sources)),
    }
