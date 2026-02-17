"""
agents/dealer_agent.py
Dealer AI Agent — combines live auction data + price models + legal docs.
"""
import logging

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are an expert Agricultural Trade AI Assistant for AgriConnect Pro, speaking with a DEALER.

Your job:
1. Provide intelligent bidding strategy and recommended price ranges.
2. Show projected profit margins BEFORE the dealer places a bid.
3. Summarise market price trends from live auction and listing data.
4. Answer legal questions using ONLY the provided legal document context.
5. Explain auction rules and transparency guarantees.

Tone: Professional, data-driven. Dealers want numbers — always show ₹ amounts and % margins."""


def _fmt_firebase(data: dict) -> str:
    if not data:
        return "No live platform data available."

    auctions = data.get("active_auctions", [])
    listings = data.get("marketplace", [])

    lines = ["🔨 ACTIVE AUCTION PRODUCTS:"]
    if auctions:
        for p in auctions[:6]:
            highest = p.get("highest_bid", p.get("base_price", "?"))
            lines.append(
                f"  • {p.get('product_name','—')} | "
                f"Base: ₹{p.get('base_price','?')} | "
                f"Highest Bid: ₹{highest} | "
                f"Qty: {p.get('quantity','?')} {p.get('unit','kg')} | "
                f"Region: {p.get('region','?')}"
            )
    else:
        lines.append("  • No active auctions.")

    lines.append("\n🛒 MARKETPLACE (price benchmark):")
    if listings:
        for item in listings[:4]:
            lines.append(
                f"  • {item.get('name','—')} | ₹{item.get('price','?')} | "
                f"Category: {item.get('category','?')}"
            )
    else:
        lines.append("  • No marketplace data.")

    return "\n".join(lines)


def dealer_response(query: str, llm=None, docs: list = None, firebase_data: dict = None) -> dict:
    firebase_str = _fmt_firebase(firebase_data or {})

    if llm is None:
        return {
            "role": "dealer",
            "answer": f"🏪 Dealer AI\n\n{firebase_str}\n\nQuery: {query}",
            "sources": [],
            "auction_snapshot": (firebase_data or {}).get("active_auctions", []),
        }

    legal_ctx = ""
    sources   = []
    if docs:
        parts = []
        for i, doc in enumerate(docs, 1):
            src = doc.metadata.get("source", "Legal Doc")
            parts.append(f"[Legal Source {i} — {src}]\n{doc.page_content.strip()}")
            sources.append(src)
        legal_ctx = "\n\n".join(parts)

    prompt = (
        f"{_SYSTEM}\n\n"
        f"--- LIVE FIREBASE DATA ---\n{firebase_str}\n\n"
        f"--- LEGAL DOCUMENT CONTEXT ---\n"
        f"{legal_ctx if legal_ctx else 'No legal documents retrieved.'}\n\n"
        f"--- DEALER QUESTION ---\n{query}\n\n"
        f"--- YOUR RESPONSE ---"
    )

    try:
        response = llm.invoke(prompt)
        answer   = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error("dealer_agent error: %s", e)
        answer = f"Error: {e}"

    return {
        "role":             "dealer",
        "answer":           answer,
        "sources":          list(set(sources)),
        "auction_snapshot": (firebase_data or {}).get("active_auctions", []),
    }
