MV.ai Debug Fixes — Local Profile + Gemini Retry + Voice Recovery

FIXED
1. Common profile questions are answered directly from user_profile.json.
2. Profile answers work even when Gemini or the internet is unavailable.
3. Gemini no longer lists models during startup, preventing startup 503 failures.
4. Transient Gemini failures retry after 1 second and 2 seconds.
5. After retries, MV.ai switches to the next fallback model.
6. Raw Gemini 503 details are replaced with a clean user-facing message.
7. AI-service errors are marked as failures instead of normal successful answers.
8. Error messages are not spoken aloud.
9. Voice returns to LISTENING//HEY MV after a failed request.

TEST
Run TEST_DEBUG_FIXES.bat, then start MV.ai with RUN_MVAI.bat.

PROFILE COMMANDS
- What do you know about me?
- What is my name?
- What is my nickname?
- What is my age?
- What projects am I building?
