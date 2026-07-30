MV.ai Memory System v0.1
========================

This patch adds explicit, editable SQLite long-term memory without merging it
with user_profile.json.

INSTALL
-------
1. Fully close MV.ai.
2. Back up your current working MV.ai_V4 folder.
3. Copy everything from this patch into MV.ai_V4.
4. Choose Replace files in the destination.
5. Keep .env, .venv, user_profile.json, and the AppData database untouched.
6. Run TEST_MEMORY_SYSTEM.bat.
7. Start MV.ai using RUN_MVAI.bat.

CHAT COMMANDS
-------------
Remember that my college documents are in Documents.
Remember that I prefer short answers.
What do you remember about college files?
What do you remember about me?
Update my preferred coding folder to Desktop/MV.ai_V4.
Forget my old gym schedule.

MEMORY TAB
----------
Open More (...) and select the brain icon.
You can search, filter, add, edit, or forget memories manually.
Forgotten memories are deactivated instead of permanently erased.

PRIVACY
-------
MV.ai refuses to store obvious passwords, API keys, OTPs, banking secrets,
private keys, seed phrases, or exact home addresses. Keep all credentials in
.env only.

ARCHITECTURE
------------
user_profile.json = manually controlled permanent profile facts
SQLite memories   = facts learned through explicit remember commands

Search in v0.1 uses exact matching, token overlap, synonym groups, and fuzzy
ranking. It does not download an embedding model or require Gemini.
