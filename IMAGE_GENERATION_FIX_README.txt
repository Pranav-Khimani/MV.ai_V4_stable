MV.ai V4 - Image-generation diagnostic fix

This patch does not magically bypass Gemini billing requirements.
It fixes the misleading "Try a clearer prompt" message and exposes the real API cause.

Install:
1. Close MV.ai.
2. Copy everything in this patch into the working MV.ai_V4 folder.
3. Replace existing files.
4. Run CHECK_IMAGE_SETUP.bat.
5. Start MV.ai from RUN_MVAI.bat and try one image request.

If the message says the free API tier is unavailable, billing must be enabled for
the Google AI project connected to GEMINI_API_KEY. Otherwise use a local image backend.
