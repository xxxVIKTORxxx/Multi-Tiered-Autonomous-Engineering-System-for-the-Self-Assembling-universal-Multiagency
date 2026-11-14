import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from crewai import LLM

# Resolve path to llm.env in the project root
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / "llm.env"


def load_llm_settings() -> dict:
    """Reloads llm.env dynamically so changes take effect without code edits."""
    if ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH, override=True)
    else:
        raise FileNotFoundError(
            f"Configuration file missing at {ENV_PATH}. Please create llm.env."
        )

    model = os.getenv("LLM_MODEL", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    max_rpm = int(os.getenv("LLM_MAX_RPM", "12"))

    if not model:
        raise ValueError("LLM_MODEL is not set in llm.env")

    return {
        "model": model,
        "api_key": api_key or "not-required",
        "base_url": base_url or None,
        "temperature": temperature,
        "max_rpm": max_rpm,
    }


def get_llm(
    temperature: Optional[float] = None,
    model_override: Optional[str] = None,
) -> LLM:
    """
    Returns a universally configured CrewAI LLM instance.
    Supports OpenRouter, Mistral, OpenAI-compatible APIs, and local Ollama.
    """
    cfg = load_llm_settings()

    chosen_model = model_override or cfg["model"]
    chosen_temp = temperature if temperature is not None else cfg["temperature"]

    llm_kwargs = {
        "model": chosen_model,
        "api_key": cfg["api_key"],
        "temperature": chosen_temp,
    }

    if cfg["base_url"]:
        llm_kwargs["base_url"] = cfg["base_url"]

    return LLM(**llm_kwargs)


def get_max_rpm() -> int:
    """Returns the configured requests-per-minute throttle for Crew execution."""
    cfg = load_llm_settings()
    return cfg["max_rpm"]


def is_verbose() -> bool:
    """Returns whether verbose agent logging is enabled in llm.env."""
    if ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH, override=True)
    return os.getenv("CREW_VERBOSE", "true").strip().lower() in ("true", "1", "yes")
