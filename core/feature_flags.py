from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
FALSE_VALUES = {"0", "false", "no", "off", "disabled"}


def reload_environment() -> None:
    """Reload the project-local .env file without exposing its contents."""

    load_dotenv(
        dotenv_path=ENV_PATH,
        override=True,
    )


def env_flag(
    name: str,
    default: bool = False,
) -> bool:
    """Read a boolean feature flag from the project-local environment."""

    reload_environment()

    raw_value = os.getenv(name)
    if raw_value is None:
        return bool(default)

    normalized = str(raw_value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False

    print(
        f"[Feature flag warning] {name}={raw_value!r} is invalid. "
        f"Using default={default}."
    )
    return bool(default)


def image_generation_enabled() -> bool:
    """Return whether paid/API image generation should be registered."""

    return env_flag(
        "MV_IMAGE_GENERATION_ENABLED",
        default=False,
    )
