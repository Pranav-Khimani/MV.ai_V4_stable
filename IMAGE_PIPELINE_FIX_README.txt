MV.ai V4 - Image Pipeline Fix

FIXED
1. Removed the unsupported forced image/png response MIME type.
2. Uses the current Gemini Interactions request shape.
3. Falls back to GenerateContent with IMAGE output enabled.
4. Keeps billing, quota, model-access, safety, and request errors separate.
5. Stops repeating the same failure twice inside the red chat bubble.

INSTALL
1. Fully close MV.ai.
2. Copy everything in this folder into the working MV.ai_V4 folder.
3. Choose Replace files in the destination.
4. Keep .env, .venv, user_profile.json, and databases.
5. Double-click TEST_IMAGE_PIPELINE_FIX.bat.
6. Start MV.ai with RUN_MVAI.bat.

POWERSHELL NOTE
PowerShell does not run files from the current directory by bare name.
Use:
    .\TEST_IMAGE_PIPELINE_FIX.bat
or simply double-click the BAT file in File Explorer.

IMPORTANT
The code bug and API access are separate issues. Gemini 3.1 image-generation
models are not available on the free Gemini Developer API tier. If the API
returns a real free-tier/billing error after this patch, code cannot bypass it.
