from __future__ import annotations

from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parent
FILES = {
    "image_tool": ROOT / "tools" / "media" / "image_generation_tools.py",
    "assistant": ROOT / "core" / "assistant.py",
    "window": ROOT / "ui" / "window.py",
}

missing = [str(path) for path in FILES.values() if not path.exists()]
if missing:
    raise FileNotFoundError(
        "Run this test from the MV.ai project folder after copying the patch. "
        f"Missing: {', '.join(missing)}"
    )

for path in FILES.values():
    py_compile.compile(str(path), doraise=True)

image_source = FILES["image_tool"].read_text(encoding="utf-8")
window_source = FILES["window"].read_text(encoding="utf-8")

# Request compatibility checks.
assert '"mime_type": "image/png"' not in image_source, (
    "The unsupported forced PNG response format is still present."
)
assert '"type": "image"' in image_source, (
    "The Interactions API image response configuration is missing."
)
assert 'response_modalities=["IMAGE"]' in image_source, (
    "The generateContent image fallback is missing."
)
assert "_extract_interaction_image" in image_source, (
    "Interactions API image extraction is missing."
)

# UI regression check: on failure the window should display report.message once,
# only falling back to the final StepResult error when report.message is empty.
assert 'message = str(report.message or "").strip()' in window_source, (
    "The single-message error display path is missing."
)
assert "for result in reversed(report.results):" in window_source, (
    "The fallback StepResult error lookup is missing."
)
assert "duplicated the same text" in window_source, (
    "The duplicate-error regression guard is missing."
)

print("[PASSED] Patched files compile.")
print("[PASSED] Forced PNG request removed.")
print("[PASSED] Interactions API image path is present.")
print("[PASSED] generateContent compatibility fallback is present.")
print("[PASSED] Duplicate red error text regression guard is present.")
print()
print("[NOTE] This test checks MV.ai's code, not whether your Gemini API tier")
print("       includes paid image-generation access.")
