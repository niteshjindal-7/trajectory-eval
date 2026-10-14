"""
config.py — Centralised settings for RxSafetyAgent

Loads all values from .env into a single settings object.
Every other module imports from here instead of calling os.getenv() directly.

Usage:
    from traj_eval.utils.config import settings

    api_key = settings.GEMINI_API_KEY
    model   = settings.GEMINI_TASK_MODEL
"""

import os
from dotenv import load_dotenv

load_dotenv()   # reads .env file from project root automatically


class Settings:

    # ── Google Gemini ─────────────────────────────────────────────────────────
    GEMINI_API_KEY: str    = os.getenv("GEMINI_API_KEY", "")
    GEMINI_TASK_MODEL: str = os.getenv("GEMINI_TASK_MODEL", "gemini-2.5-flash")
    GEMINI_EVAL_MODEL: str = os.getenv("GEMINI_EVAL_MODEL", "gemini-2.5-pro")

    # ── LangFuse Observability ────────────────────────────────────────────────
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str       = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    # ── OpenFDA ───────────────────────────────────────────────────────────────
    OPENFDA_API_KEY: str = os.getenv("OPENFDA_API_KEY", "")
    # Optional — increases rate limit from 240 to 1000 req/min

    # ── Experiment Settings ───────────────────────────────────────────────────
    MAX_STEPS: int       = int(os.getenv("MAX_STEPS", "10"))
    EXPERIMENT_NAME: str = os.getenv("EXPERIMENT_NAME", "exp_001_evaluator_v1")


settings = Settings()
