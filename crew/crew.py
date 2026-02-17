"""
crew/crew.py
AgriConnect Pro Crew Orchestrator.

IMPORTANT: Always access db and llm via the module object (import rag.rag_chain as rc),
never via `from rag.rag_chain import llm` — the latter captures None at import
time before init_rag() has run.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _get_llm():
    import rag.rag_chain as rc
    return rc.llm

def _get_db():
    import rag.rag_chain as rc
    return rc.db


def run_crew(
    query:   str,
    role:    str,
    user_id: Optional[str] = None,
    region:  Optional[str] = None,
) -> dict:
    from agents.retriever          import retrieve
    from agents.compliance_checker import check
    from agents.farmer_agent       import farmer_response
    from agents.dealer_agent       import dealer_response
    from agents.user_agent         import user_response
    from app.queries               import get_farmer_context, get_dealer_context, get_user_context

    llm = _get_llm()
    db  = _get_db()

    # ── Step 1: Legal document retrieval ──────────────────────────────────────
    docs = retrieve(query, db) if db else []

    # ── Step 2: Role-scoped Firebase data ─────────────────────────────────────
    firebase_data: dict = {}
    if role == "farmer":
        firebase_data = get_farmer_context(user_id=user_id or "", region=region)
    elif role == "dealer":
        firebase_data = get_dealer_context(region=region)
    else:
        firebase_data = get_user_context()

    # ── Step 3: Role agent ────────────────────────────────────────────────────
    if role == "farmer":
        result = farmer_response(query=query, llm=llm, docs=docs, firebase_data=firebase_data)
    elif role == "dealer":
        result = dealer_response(query=query, llm=llm, docs=docs, firebase_data=firebase_data)
    else:
        result = user_response(query=query, llm=llm, docs=docs, firebase_data=firebase_data)

    # ── Step 4: Compliance check ──────────────────────────────────────────────
    compliance = check(result.get("answer", ""), docs)

    # ── Step 5: Final response ────────────────────────────────────────────────
    response = {
        "role":       role,
        "answer":     result.get("answer", ""),
        "sources":    result.get("sources", []),
        "compliance": compliance,
    }
    if role == "farmer" and "iot_snapshot" in result:
        response["iot_snapshot"] = result["iot_snapshot"]
    if role == "dealer" and "auction_snapshot" in result:
        response["auction_snapshot"] = result["auction_snapshot"]

    return response