"""
config.py — Centralised settings for RxSafetyAgent

Loads all values from .env into a single config object.
Every other module imports from here instead of calling os.getenv() directly.

Usage:
    from traj_eval.utils.config import config

    api_key = config.GEMINI_API_KEY
    model   = config.GEMINI_TASK_MODEL
"""

import os
from dotenv import load_dotenv

load_dotenv()   # reads .env file from project root automatically


class Config:

    # ── LLM Provider Switch ───────────────────────────────────────────────────
    LLM_PROVIDER: str      = os.getenv("LLM_PROVIDER", "gemini")
    # Set to "gemini" or "openai" in .env to switch providers

    # ── Google Gemini ─────────────────────────────────────────────────────────
    GEMINI_API_KEY: str    = os.getenv("GEMINI_API_KEY", "")
    GEMINI_TASK_MODEL: str = os.getenv("GEMINI_TASK_MODEL", "gemini-3.1-flash-lite")
    GEMINI_EVAL_MODEL: str = os.getenv("GEMINI_EVAL_MODEL", "gemini-3.1-flash-lite")

    # ── OpenAI ────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str    = os.getenv("OPENAI_API_KEY", "")
    OPENAI_TASK_MODEL: str = os.getenv("OPENAI_TASK_MODEL", "gpt-4o-mini")
    OPENAI_EVAL_MODEL: str = os.getenv("OPENAI_EVAL_MODEL", "gpt-4o")

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


config = Config()
