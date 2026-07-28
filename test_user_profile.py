from pathlib import Path

from memory.user_profile import UserProfile


profile_path = Path(__file__).resolve().parent / "user_profile.json"
profile = UserProfile(profile_path)
context = profile.get_context()
status = profile.get_status()

print(context)
print("\nStatus:", status)

if not status.get("ready"):
    raise SystemExit("[FAILED] Profile file is invalid.")

if "personal.name: Pranav" not in context:
    raise SystemExit("[FAILED] The default name was not loaded.")

print("\n[PASSED] Editable user profile is working.")
