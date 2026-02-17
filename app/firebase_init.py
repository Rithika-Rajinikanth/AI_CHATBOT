"""
app/firebase_init.py
Initialises Firebase Admin SDK once at startup.

Exports:
    firestore_db  → Cloud Firestore client
    realtime_db   → Realtime Database root reference
"""
import os
import logging
import firebase_admin
from firebase_admin import credentials, firestore, db as rtdb

from app.config import settings

logger = logging.getLogger(__name__)

_initialized  = False
firestore_db  = None
realtime_db   = None


def init_firebase() -> None:
    """Call once inside FastAPI lifespan startup."""
    global _initialized, firestore_db, realtime_db

    if _initialized:
        return

    cred_path = settings.FIREBASE_CREDENTIALS
    if not os.path.exists(cred_path):
        logger.warning(
            "Firebase credentials '%s' not found — Firebase queries will return empty data.", cred_path
        )
        return

    try:
        options = {}
        if settings.FIREBASE_RTDB_URL:
            options["databaseURL"] = settings.FIREBASE_RTDB_URL

        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, options)

        firestore_db = firestore.client()
        realtime_db  = rtdb.reference("/") if settings.FIREBASE_RTDB_URL else None
        _initialized = True
        logger.info("✅ Firebase initialised.")
    except Exception as e:
        logger.error("❌ Firebase init failed: %s", e)
