from __future__ import annotations

import sys
from pathlib import Path


KEY = "MV_IMAGE_GENERATION_ENABLED"


def update_env(enabled: bool) -> Path:
    root = Path(__file__).resolve().parent
    env_path = root / ".env"
    desired = "true" if enabled else "false"

    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    output: list[str] = []
    replaced = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{KEY}="):
            if not replaced:
                output.append(f"{KEY}={desired}")
                replaced = True
            continue
        output.append(line)

    if not replaced:
        if output and output[-1].strip():
            output.append("")
        output.append(f"{KEY}={desired}")

    env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    return env_path


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1].strip().lower() not in {
        "true", "false", "1", "0", "on", "off", "yes", "no"
    }:
        print("Usage: python set_image_generation.py true|false")
        return 2

    enabled = sys.argv[1].strip().lower() in {"true", "1", "on", "yes"}
    env_path = update_env(enabled)

    print(f"[MV.ai] Image generation is now {'ENABLED' if enabled else 'DISABLED'}.")
    print(f"[MV.ai] Updated: {env_path}")
    print("[MV.ai] Restart MV.ai for the change to take effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
