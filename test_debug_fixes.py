from pathlib import Path

from memory.user_profile import UserProfile


profile = UserProfile(Path(__file__).resolve().parent / "user_profile.json")

checks = {
    "Can you tell me everything you know abt me?": "Here is what I know",
    "What is my name?": "Pranav",
    "What is my nickname?": "Multiverse",
    "What is my age?": "16",
    "What projects am I building?": "MV.ai",
}

for question, expected in checks.items():
    answer = profile.answer_query(question)
    if answer is None or expected.lower() not in answer.lower():
        raise SystemExit(
            f"[FAILED] {question!r} returned {answer!r}; "
            f"expected text containing {expected!r}."
        )

if profile.answer_query("Open YouTube") is not None:
    raise SystemExit("[FAILED] Non-profile commands were intercepted.")

print("[PASSED] Local profile answers work without Gemini.")
print("[INFO] Gemini retry and voice recovery are checked at runtime.")
