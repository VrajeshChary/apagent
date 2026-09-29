"""
Configuration settings for the Invoice Exception Resolution Agent.
"""
import os
from dotenv import load_dotenv

load_dotenv()


# ── Groq LLM ──────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen-qwq-32b")  # or llama-3.3-70b-versatile

# ── Hindsight API (remote) ─────────────────────────────────────────────
HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY", "")
HINDSIGHT_BASE_URL = os.getenv("HINDSIGHT_BASE_URL", "https://hindsight.api.example.com")

# ── Local ChromaDB fallback ────────────────────────────────────────────
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma_db")
USE_LOCAL_HINDSIGHT = os.getenv("USE_LOCAL_HINDSIGHT", "true").lower() == "true"

# ── Exception thresholds ──────────────────────────────────────────────
AUTO_APPROVE_THRESHOLD = 500       # auto-approve variances under this amount
ESCALATION_THRESHOLD = 5000        # escalate variances over this amount
CONFIDENCE_THRESHOLD = 0.75        # minimum confidence for auto-resolution

# ── Vendor risk tiers ────────────────────────────────────────────────
VENDOR_RISK_TIERS = {
    "low":    {"max_auto_approve": 1000, "review_required": False},
    "medium": {"max_auto_approve": 500,  "review_required": False},
    "high":   {"max_auto_approve": 100,  "review_required": True},
}
