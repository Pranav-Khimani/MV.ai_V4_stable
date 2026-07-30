MV.ai V4 - Image Generation v0.1
================================

This patch was built from the uploaded MV.ai_V4(3) source.
It does not include .env, .venv, user_profile.json, databases, logs, or Git data.

INSTALL
-------
1. Fully close MV.ai.
2. Back up the current working MV.ai_V4 folder.
3. Copy everything inside this patch folder into MV.ai_V4.
4. Choose "Replace files in the destination".
5. Do not delete .env, .venv, user_profile.json, or the memory database.
6. Run INSTALL_IMAGE_GENERATION.bat once.
7. Run TEST_IMAGE_GENERATION.bat.
8. Start MV.ai with RUN_MVAI.bat.

TEST COMMANDS
-------------
Generate an image of a futuristic purple city at night.
Create a square minimal logo concept for MV.ai.
Make a portrait illustration of a robot librarian.
Generate a 16:9 cinematic space station wallpaper in 2K.

WHAT IT ADDS
------------
- Schema-registered images tool with generate_image action.
- Reliable local routing for clear image-generation commands.
- Gemini image model retry and fallback.
- 1:1, 3:2, 2:3, 4:3, 3:4, 4:5, 5:4, 16:9, 9:16, 21:9.
- 1K, 2K, and 4K requests where supported.
- Generated images saved in MV.ai's private AppData media folder.
- Generated image displayed directly in the chat.
- Click-to-preview, Save as, Copy image, and Open folder buttons.
- Generated images and prompts restored with saved Realities.
- Voice says only: "Your image is ready."

NOTES
-----
- Image generation requires internet access and GEMINI_API_KEY in .env.
- The first image may take longer than a normal text response.
- Cancelling stops MV.ai from displaying/saving the result, but an API request
  already in progress may finish on Google's side before it can be discarded.
- The original attached-image analysis feature remains unchanged.
