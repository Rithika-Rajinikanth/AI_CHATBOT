"""
main.py — AgriConnect Pro  AI Legal + Agricultural Chatbot
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field

from app.auth        import get_current_user, TokenPayload
from app.auth_routes import auth_router
from app.audit       import audit_middleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 AgriConnect Pro starting …")
    try:
        from app.firebase_init import init_firebase
        init_firebase()
    except Exception as e:
        logger.error("Firebase init error (non-fatal): %s", e)
    try:
        from rag.rag_chain import init_rag
        init_rag()
    except Exception as e:
        logger.error("RAG init error (non-fatal): %s", e)
    logger.info("✅ All systems ready.")
    yield
    logger.info("🛑 Shutdown complete.")


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AgriConnect Pro — AI Legal Chatbot",
    description="""
## How to authenticate in Swagger

1. **POST `/auth/login`** → copy the `access_token`
2. Click 🔒 **Authorize** (top-right)
3. Paste the token → **Authorize** → **Close**
4. All routes now send the token automatically ✅

---

## Roles
| Role | Username (Firebase UID) | Password (role string) |
|------|------------------------|------------------------|
| Farmer | DIAckepAiQcR592cPUztHlMXQCD2 | farmer |
| Dealer | any_dealer_firebase_uid | dealer |
| User   | any_user_firebase_uid  | user |
""",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(audit_middleware)
app.include_router(auth_router, prefix="/auth")


# ── OpenAPI: add BearerAuth lock icon on every route ──────────────────────────
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})
    schema["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi


# ── Response models ────────────────────────────────────────────────────────────
class ComplianceResult(BaseModel):
    status: str
    score:  float
    detail: str

class ChatResponse(BaseModel):
    role:             str
    answer:           str
    sources:          List[str]
    compliance:       ComplianceResult
    iot_snapshot:     Optional[dict]     = None
    auction_snapshot: Optional[List]     = None

class ObligationResponse(BaseModel):
    role:        str
    obligations: List[str]

class CompareResponse(BaseModel):
    role:       str
    query_a:    str
    query_b:    str
    diff_count: int
    diffs:      List[dict]

class HealthResponse(BaseModel):
    status:         str
    version:        str
    llm_model:      str
    ollama_url:     str
    rag_ready:      bool
    llm_ready:      bool
    firebase_ready: bool


# ── Request models ─────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str          = Field(..., min_length=3)
    region:   Optional[str] = Field(None)

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What is the best price to sell my rice crop today?",
                "region":   "Karnataka",
            }
        }

class ObligationRequest(BaseModel):
    text: str = Field(..., min_length=10)

    class Config:
        json_schema_extra = {
            "example": {
                "text": (
                    "The Farmer SHALL provide accurate crop data at all times. "
                    "The Company MUST ensure 99.5% platform uptime. "
                    "Users are REQUIRED to comply with Indian agricultural trade laws."
                )
            }
        }

class CompareRequest(BaseModel):
    query_a: str
    query_b: str

    class Config:
        json_schema_extra = {
            "example": {
                "query_a": "farmer obligations and rights in the auction system",
                "query_b": "dealer obligations and bidding rules",
            }
        }


# ── Helper: get live llm/db from rag_chain module (not stale import) ──────────
def _get_llm():
    """
    Always read from the module object — never from a cached import.
    `from rag.rag_chain import llm` captures the value at import time (None).
    `import rag.rag_chain; rag.rag_chain.llm` reads the live object after init_rag().
    """
    import rag.rag_chain as rc
    return rc.llm

def _get_db():
    import rag.rag_chain as rc
    return rc.db


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"], response_model=HealthResponse)
def health():
    """System readiness — **no auth required**. Check this first after startup."""
    from app.firebase_init import firestore_db
    from app.config        import settings
    return {
        "status":         "ok",
        "version":        "2.1.0",
        "llm_model":      settings.OLLAMA_MODEL,
        "ollama_url":     settings.OLLAMA_BASE_URL,
        "rag_ready":      _get_db()  is not None,
        "llm_ready":      _get_llm() is not None,
        "firebase_ready": firestore_db is not None,
    }


@app.post("/chat", tags=["Chat"], response_model=ChatResponse)
def chat(
    body: ChatRequest,
    user: TokenPayload = Depends(get_current_user),
):
    """
    **Role-aware chat.**

    Your role and Firebase UID come from the JWT — only send `question` + optional `region`.

    Sample questions:
    - **Farmer:** `What is the best price to sell my rice crop today?`
    - **Dealer:** `What is the recommended bid range for wheat in Karnataka?`
    - **User:**   `How does the platform protect my personal data?`
    """
    from crew.crew import run_crew
    logger.info("chat | user=%s role=%s | q=%.60s", user.sub, user.role, body.question)
    return run_crew(
        query=body.question,
        role=user.role,
        user_id=user.sub,
        region=body.region,
    )


@app.post("/obligations", tags=["Legal Tools"], response_model=ObligationResponse)
def extract_obligations(
    body: ObligationRequest,
    user: TokenPayload = Depends(get_current_user),
):
    """
    **Extract legal obligations** (SHALL / MUST / REQUIRED / OBLIGATED) from any text.

    Returns bullet points with the responsible party.

    **Sample input:**
    ```
    The Farmer SHALL provide accurate crop data at all times.
    The Company MUST ensure 99.5% platform uptime.
    Users are REQUIRED to comply with Indian agricultural trade laws.
    ```
    """
    from agents.obligation_extractor import extract

    llm = _get_llm()   # ← read live module attribute, not stale import

    if llm is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Ollama LLM is not running. "
                "Open a terminal and run:  ollama serve"
            ),
        )

    try:
        obligations = extract(llm, body.text)
    except Exception as e:
        logger.error("obligations route error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}",
        )

    return {"role": user.role, "obligations": obligations}


@app.post("/compare", tags=["Legal Tools"], response_model=CompareResponse)
def compare_contracts(
    body: CompareRequest,
    user: TokenPayload = Depends(get_current_user),
):
    """
    **Compare two contract sections** from your legal PDFs side-by-side.

    Sample:
    - `query_a`: `farmer obligations auction`
    - `query_b`: `dealer obligations bidding`
    """
    from agents.retriever        import retrieve
    from agents.contract_compare import compare

    db = _get_db()   # ← read live module attribute

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FAISS index not loaded. Run: python -m rag.ingest",
        )

    try:
        diffs = compare(retrieve(body.query_a, db, k=4), retrieve(body.query_b, db, k=4))
    except Exception as e:
        logger.error("compare route error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compare failed: {str(e)}",
        )

    return {
        "role": user.role, "query_a": body.query_a,
        "query_b": body.query_b, "diff_count": len(diffs), "diffs": diffs,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)