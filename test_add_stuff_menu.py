from pathlib import Path

window_file = Path(__file__).parent / "ui" / "window.py"
source = window_file.read_text(encoding="utf-8")

required = [
    'QPushButton("+")',
    'def toggle_add_stuff_popup',
    'def show_add_stuff_popup',
    'QPushButton("＋   Add files")',
    'Qt.WindowType.Popup',
]

missing = [item for item in required if item not in source]
if missing:
    raise SystemExit(f"[FAILED] Missing compact ADD Stuff menu code: {missing}")

compile(source, str(window_file), "exec")
print("[PASSED] Compact + button and Add files popup are present.")
print("[PASSED] ui/window.py compiles successfully.")
