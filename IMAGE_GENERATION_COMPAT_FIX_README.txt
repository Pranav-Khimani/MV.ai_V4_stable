MV.ai V4 - Image Generation Compatibility Fix

WHY THIS PATCH EXISTS
The earlier image tool always sent response configuration fields first. On some
Gemini API / google-genai combinations that request is rejected with HTTP 400,
even for a basic prompt such as "generate an image of a cat".

WHAT CHANGED
- Default 1:1 / 1K images now use Google's simplest documented
  models.generate_content request with no optional configuration.
- If custom aspect-ratio/size configuration is rejected, MV.ai automatically
  retries with compatibility mode instead of blaming the prompt.
- Generated image extraction now supports both response.parts and
  response.candidates[0].content.parts SDK shapes.
- Text extraction no longer relies on response.text when the response contains
  image parts.

INSTALL
1. Close MV.ai.
2. Copy the tools folder into the working MV.ai_V4 folder.
3. Replace the existing file when Windows asks.
4. Start MV.ai using RUN_MVAI.bat.
5. Test: Generate an image of a cute cat.

If the next error mentions billing, quota, or access, the request format is fixed
and the remaining issue is the Google API project rather than the prompt/code.
