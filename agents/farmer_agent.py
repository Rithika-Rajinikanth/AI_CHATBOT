"""
agents/farmer_agent.py
Farmer AI Agent — combines IoT sensor data + auction listings + legal docs.
"""
import logging

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are an expert Agricultural AI Assistant for AgriConnect Pro, speaking with a FARMER.

Your job:
1. Analyse live IoT sensor readings and give actionable crop health advice.
2. Recommend the best sell price based on current auction bids and market data.
3. Answer legal questions using ONLY the provided legal document context.
4. Guide the farmer through the auction process.

Tone: Friendly, practical, concise. Use simple language. Always suggest next steps."""


def _fmt_firebase(data: dict) -> str:
    if not data:
        return "No live platform data available."

    iot      = data.get("iot_data", {})
    auctions = data.get("my_auctions", [])
    listings = data.get("all_listings", [])

    lines = ["📡 IoT SENSOR READINGS:"]
    if iot:
        for k, v in iot.items():
            lines.append(f"  • {k.replace('_', ' ').title()}: {v}")
    else:
        lines.append("  • No sensor data available.")

    lines.append("\n🏷️  YOUR ACTIVE AUCTION LISTINGS:")
    if auctions:
        for p in auctions[:5]:
            lines.append(
                f"  • {p.get('product_name','—')} | "
                f"Base: ₹{p.get('base_price','?')} | "
                f"Highest Bid: ₹{p.get('highest_bid', p.get('base_price','?'))} | "
                f"Bids: {p.get('bid_count', 0)}"
            )
    else:
        lines.append("  • No active listings.")

    lines.append("\n🛒 MARKETPLACE SNAPSHOT:")
    if listings:
        for item in listings[:4]:
            lines.append(
                f"  • {item.get('name','—')} | ₹{item.get('price','?')} | "
                f"Category: {item.get('category','?')}"
            )
    else:
        lines.append("  • No marketplace data.")

    return "\n".join(lines)


def farmer_response(query: str, llm=None, docs: list = None, firebase_data: dict = None) -> dict:
    firebase_str = _fmt_firebase(firebase_data or {})

    if llm is None:
        return {
            "role": "farmer",
            "answer": f"👨‍🌾 Farmer AI\n\n{firebase_str}\n\nQuery: {query}",
            "sources": [],
            "iot_snapshot": (firebase_data or {}).get("iot_data", {}),
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
        f"--- FARMER QUESTION ---\n{query}\n\n"
        f"--- YOUR RESPONSE ---"
    )

    try:
        response = llm.invoke(prompt)
        answer   = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        logger.error("farmer_agent error: %s", e)
        answer = f"Error: {e}"

    return {
        "role":         "farmer",
        "answer":       answer,
        "sources":      list(set(sources)),
        "iot_snapshot": (firebase_data or {}).get("iot_data", {}),
    }
