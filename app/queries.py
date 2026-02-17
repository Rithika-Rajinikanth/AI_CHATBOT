"""
app/queries.py
All Firebase data-access functions.

Role-scoped context builders:
  get_farmer_context(user_id, region)  → IoT + auctions + listings
  get_dealer_context(region)           → auctions + listings
  get_user_context()                   → marketplace listings only
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _fs():
    from app.firebase_init import firestore_db
    return firestore_db


def _rt():
    from app.firebase_init import realtime_db
    return realtime_db


# ── Basic queries ──────────────────────────────────────────────────────────────

def get_user(user_id: str) -> Optional[dict]:
    try:
        db = _fs()
        if db is None:
            return None
        doc = db.collection("users").document(user_id).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        logger.error("get_user: %s", e)
        return None


def get_marketplace_listings(category: Optional[str] = None) -> list:
    try:
        db = _fs()
        if db is None:
            return []
        q = db.collection("listings")
        if category:
            q = q.where("category", "==", category)
        return [d.to_dict() for d in q.stream()]
    except Exception as e:
        logger.error("get_marketplace_listings: %s", e)
        return []


def get_product_by_id(product_id: str) -> Optional[dict]:
    try:
        db = _fs()
        if db is None:
            return None
        doc = db.collection("products").document(product_id).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        logger.error("get_product_by_id: %s", e)
        return None


def get_iot_data(farmer_id: str) -> dict:
    """Reads /iot/{farmer_id}/ from Firebase Realtime Database."""
    try:
        ref = _rt()
        if ref is None:
            return {}
        data = ref.child("iot").child(farmer_id).get()
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.error("get_iot_data: %s", e)
        return {}


def get_auction_products(region: Optional[str] = None) -> list:
    try:
        db = _fs()
        if db is None:
            return []
        q = db.collection("auction_products").where("status", "==", "active")
        if region:
            q = q.where("region", "==", region)
        return [d.to_dict() for d in q.stream()]
    except Exception as e:
        logger.error("get_auction_products: %s", e)
        return []


def get_live_bids(product_id: str) -> list:
    try:
        db = _fs()
        if db is None:
            return []
        bids = (
            db.collection("bids")
            .where("product_id", "==", product_id)
            .order_by("amount", direction="DESCENDING")
            .stream()
        )
        return [b.to_dict() for b in bids]
    except Exception as e:
        logger.error("get_live_bids: %s", e)
        return []


# ── Role-scoped context builders ───────────────────────────────────────────────

def get_farmer_context(user_id: str, region: Optional[str] = None) -> dict:
    """
    Everything a Farmer agent needs:
      - Live IoT sensor readings for this farmer
      - Auction products this farmer has listed
      - Recent marketplace listings
    """
    iot      = get_iot_data(user_id)
    auctions = get_auction_products(region)
    listings = get_marketplace_listings()

    my_auctions = [p for p in auctions if p.get("farmer_id") == user_id]

    return {
        "iot_data":     iot,
        "my_auctions":  my_auctions,
        "all_listings": listings[:10],
    }


def get_dealer_context(region: Optional[str] = None) -> dict:
    """
    Everything a Dealer agent needs:
      - All active auction products (with highest bids)
      - Marketplace listings for price benchmarking
    """
    return {
        "active_auctions": get_auction_products(region),
        "marketplace":     get_marketplace_listings()[:10],
    }


def get_user_context() -> dict:
    """General user — marketplace listings only, no IoT or bid data."""
    return {"all_listings": get_marketplace_listings()}
