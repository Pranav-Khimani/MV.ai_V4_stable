MV.ai Vision Input v0.1
========================

WHAT THIS ADDS
- A button named exactly: ADD Stuff!
- Select one PNG, JPG, JPEG, or WebP image.
- Preview the selected image before sending.
- Remove or replace the staged image.
- Ask a question about the image.
- Show the image inside the user chat bubble.
- Click a chat image to open a larger preview.
- Copy sent images into MV.ai's private AppData media folder.
- Restore attached images when an old Reality is reopened.
- Retry temporary Gemini errors and switch fallback models.

CURRENT LIMITS
- One image per message in v0.1.
- Maximum image size: 18 MB.
- This patch analyzes images only.
- Image generation and image editing are separate later phases.
- Attached images are sent to Google's Gemini service when you press Send.
- Clearing Realities does not yet automatically delete orphaned media files.

INSTALL
1. Close MV.ai.
2. Copy this patch over the matching folders in your working MV.ai_V4 project.
3. Keep your .env, .venv, user_profile.json, and database.
4. Run TEST_IMAGE_SUPPORT.bat.
5. Start MV.ai with RUN_MVAI.bat.

USE
1. Click ADD Stuff!
2. Select an image.
3. Type a question such as:
   - Explain this screenshot.
   - What error is shown here?
   - Describe this design.
   - Read the visible text.
4. Press Send.
