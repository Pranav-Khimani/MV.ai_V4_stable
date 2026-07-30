from __future__ import annotations

import importlib.metadata
import os
from dotenv import load_dotenv


def main() -> int:
    load_dotenv(override=True)
    key = os.getenv("GEMINI_API_KEY", "").strip()
    try:
        version = importlib.metadata.version("google-genai")
    except importlib.metadata.PackageNotFoundError:
        print("[FAILED] google-genai is not installed.")
        return 1

    print(f"[INFO] google-genai version: {version}")
    print(f"[INFO] GEMINI_API_KEY loaded: {bool(key)}")

    from google import genai

    client = genai.Client(api_key=key or "missing")
    interactions = getattr(client, "interactions", None)
    supported = interactions is not None and hasattr(interactions, "create")
    print(f"[INFO] Interactions image API available in SDK: {supported}")

    if not key:
        print("[FAILED] Add GEMINI_API_KEY to .env.")
        return 1
    if not supported:
        print("[FAILED] Run INSTALL_IMAGE_GENERATION.bat to update google-genai.")
        return 1

    print("[PASSED] Local image-generation setup is installed.")
    print("[NOTE] This check does not make a paid image request.")
    print("[NOTE] Gemini image-generation models require a paid API tier.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
