MV.ai V4 — Image Pipeline Test Fix

WHAT THIS FIXES
- Replaces a brittle test assertion that searched for an exact comment inside
  core/assistant.py.
- The old test could fail even when the runtime duplicate-error fix was present.
- This patch does not change MV.ai's runtime image-generation code.

INSTALL
1. Close MV.ai.
2. Copy these two test files into the root of your working MV.ai_V4 folder.
3. Replace the old files when Windows asks.
4. Double-click TEST_IMAGE_PIPELINE_FIX.bat.

IMPORTANT
A passing test means the code pipeline is installed correctly. It does not grant
Gemini image-generation access. Your current API response says the project is on
a tier without image-generation access.
