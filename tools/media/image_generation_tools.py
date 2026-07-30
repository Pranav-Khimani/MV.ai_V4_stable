from __future__ import annotations

import base64
import os
import re
import time
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from core.media_store import MediaStore
from core.tool import Tool
from core.tool_schema import ActionSchema


load_dotenv()


class ImageGenerationTool(Tool):
    """Generate an image from a text prompt and save it locally."""

    name = "images"
    description = "Generate original images from detailed text prompts."
    supported_devices = ("laptop",)
    prompt_rules = (
        "Use this tool when the user asks to generate, create, draw, design, render, or make an image, picture, poster, wallpaper, logo concept, illustration, or visual.",
        "Do not use this tool merely to describe or analyze an attached image.",
        "Preserve the user's requested subject, style, colors, composition, visible text, and restrictions in the prompt.",
        "Do not claim the image was generated until the tool returns successfully.",
    )
    actions = {
        "generate_image": ActionSchema(
            description="Generate one image from a text prompt and save it in MV.ai's private media folder.",
            required_arguments=("prompt",),
            optional_arguments=("aspect_ratio", "image_size"),
            example={
                "prompt": "A minimal single-color geometric logo for an AI assistant, no letters, dark background",
                "aspect_ratio": "1:1",
                "image_size": "1K",
            },
            prompt_rules=(
                "The prompt must contain only the requested visual instructions, not planning commentary.",
                "Use aspect_ratio only when the user requests a shape or format. Supported values: 1:1, 3:2, 2:3, 4:3, 3:4, 4:5, 5:4, 16:9, 9:16, 21:9.",
                "Use image_size only when explicitly requested. Supported values: 1K, 2K, and 4K. Default to 1K.",
            ),
        )
    }

    IMAGE_MODELS = (
        "gemini-3.1-flash-image",
        "gemini-3.1-flash-lite-image",
        "gemini-2.5-flash-image",
    )
    RETRY_DELAYS_SECONDS = (0.0, 1.0, 2.0)
    RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
    VALID_ASPECT_RATIOS = {
        "1:1", "3:2", "2:3", "4:3", "3:4",
        "4:5", "5:4", "16:9", "9:16", "21:9",
    }
    VALID_IMAGE_SIZES = {"1K", "2K", "4K"}

    def __init__(self) -> None:
        self.media_store = MediaStore()
        self.client = None
        self.initialization_error = ""

        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            self.initialization_error = (
                "Image generation is not configured. Add GEMINI_API_KEY "
                "to your local .env file."
            )
            return

        try:
            self.client = genai.Client(api_key=api_key)
        except Exception as error:
            self.initialization_error = self._friendly_error(error)

    def execute(self, args=None):
        args = dict(args or {})
        action = str(args.get("action", "")).strip().lower()
        if action != "generate_image":
            raise ValueError(f"Unsupported image action: {action or 'missing action'}")

        prompt = str(args.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("Tell MV.ai what image to generate.")

        aspect_ratio = self._normalize_aspect_ratio(args.get("aspect_ratio"))
        image_size = self._normalize_image_size(args.get("image_size"))

        if self.client is None:
            raise RuntimeError(
                self.initialization_error
                or "Image generation is temporarily unavailable."
            )

        last_error: Exception | None = None
        for model_name in self.IMAGE_MODELS:
            for attempt, delay in enumerate(self.RETRY_DELAYS_SECONDS, start=1):
                if delay:
                    time.sleep(delay)

                try:
                    effective_size = (
                        "1K"
                        if model_name in {
                            "gemini-3.1-flash-lite-image",
                            "gemini-2.5-flash-image",
                        }
                        else image_size
                    )
                    image_bytes, mime_type, output_text = self._generate_with_model(
                        model_name=model_name,
                        prompt=prompt,
                        aspect_ratio=aspect_ratio,
                        image_size=effective_size,
                    )
                    attachment = self.media_store.store_generated_image(
                        image_bytes=image_bytes,
                        mime_type=mime_type,
                        prompt=prompt,
                        model=model_name,
                        aspect_ratio=aspect_ratio,
                        image_size=effective_size,
                    )
                    attachment["requested_image_size"] = image_size
                    attachment["display_text"] = (
                        output_text.strip() if output_text.strip() else "Your image is ready."
                    )
                    return attachment

                except errors.APIError as error:
                    last_error = error
                    status = self._status_code(error)
                    error_text = self._error_blob(error)
                    print(
                        f"[IMAGE API ERROR] model={model_name} "
                        f"attempt={attempt} status={status}: {error_text}"
                    )

                    # A free-tier limit of zero or a billing/access failure will
                    # not improve by retrying the same request across models.
                    if self._requires_billing(error):
                        raise RuntimeError(self._friendly_error(error)) from error

                    if status == 404:
                        break
                    if status in self.RETRYABLE_STATUS_CODES and attempt < len(self.RETRY_DELAYS_SECONDS):
                        continue
                    if status in self.RETRYABLE_STATUS_CODES:
                        break
                    raise RuntimeError(self._friendly_error(error)) from error

                except Exception as error:
                    last_error = error
                    message = self._error_blob(error).lower()
                    print(
                        f"[IMAGE GENERATION ERROR] model={model_name} "
                        f"attempt={attempt}: {self._error_blob(error)}"
                    )

                    if self._requires_billing(error):
                        raise RuntimeError(self._friendly_error(error)) from error
                    if "not found" in message or "unsupported" in message:
                        break
                    if self._looks_retryable(error) and attempt < len(self.RETRY_DELAYS_SECONDS):
                        continue
                    if self._looks_retryable(error):
                        break
                    raise RuntimeError(self._friendly_error(error)) from error

        if last_error is not None:
            print(f"[Image generation unavailable] {last_error}")
        raise RuntimeError(
            "Image generation is temporarily unavailable. Try again shortly."
        )

    def _generate_with_model(
        self,
        model_name: str,
        prompt: str,
        aspect_ratio: str,
        image_size: str,
    ) -> tuple[bytes, str, str]:
        """Generate one image using Google's current API shape.

        The Interactions API is the primary path for Gemini 3 image models.
        Crucially, MV.ai does not force a PNG response MIME type: the API
        currently chooses a supported image encoding itself.  Older SDKs
        fall back to ``models.generate_content`` with IMAGE output enabled.
        """

        interactions = getattr(self.client, "interactions", None)
        if interactions is not None and hasattr(interactions, "create"):
            try:
                request: dict[str, Any] = {
                    "model": model_name,
                    "input": prompt,
                }

                # Default generation already produces a 1:1 image. Only send
                # response_format when the user actually asks for controls.
                if aspect_ratio != "1:1" or image_size != "1K":
                    request["response_format"] = {
                        "type": "image",
                        "aspect_ratio": aspect_ratio,
                        "image_size": image_size,
                    }

                interaction = interactions.create(**request)
                image_bytes, mime_type = self._extract_interaction_image(
                    interaction
                )
                output_text = str(
                    getattr(interaction, "output_text", "") or ""
                ).strip()
                if image_bytes:
                    return image_bytes, mime_type, output_text

                raise RuntimeError(
                    output_text
                    or f"{model_name} returned no generated image."
                )

            except errors.APIError as error:
                # Real API failures (billing, quota, permissions, safety,
                # model access) must keep their original status and message.
                # Only a custom-format 400 gets one compatibility retry using
                # the model defaults.
                if (
                    self._status_code(error) == 400
                    and (aspect_ratio != "1:1" or image_size != "1K")
                ):
                    print(
                        "[IMAGE COMPATIBILITY] Custom size/aspect settings "
                        f"were rejected for {model_name}; retrying defaults."
                    )
                    interaction = interactions.create(
                        model=model_name,
                        input=prompt,
                    )
                    image_bytes, mime_type = self._extract_interaction_image(
                        interaction
                    )
                    output_text = str(
                        getattr(interaction, "output_text", "") or ""
                    ).strip()
                    if image_bytes:
                        return image_bytes, mime_type, output_text
                raise

            except (AttributeError, TypeError, ValueError) as error:
                # Local SDK mismatch: continue to the legacy generateContent
                # compatibility path below.
                print(
                    "[IMAGE COMPATIBILITY] Interactions API unavailable or "
                    f"incompatible for {model_name}: {error}"
                )

        return self._generate_with_generate_content(
            model_name=model_name,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )

    def _generate_with_generate_content(
        self,
        model_name: str,
        prompt: str,
        aspect_ratio: str,
        image_size: str,
    ) -> tuple[bytes, str, str]:
        """Compatibility path for SDK builds without Interactions support."""

        config = None
        try:
            image_config_type = getattr(types, "ImageConfig", None)
            if image_config_type is not None:
                config = types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=image_config_type(
                        aspect_ratio=aspect_ratio,
                        image_size=image_size,
                    ),
                )
            else:
                config = types.GenerateContentConfig(
                    response_modalities=["IMAGE"]
                )
        except (AttributeError, TypeError, ValueError):
            # Some older SDK builds accept a plain dictionary instead.
            config = {"response_modalities": ["IMAGE"]}

        response = self.client.models.generate_content(
            model=model_name,
            contents=[prompt],
            config=config,
        )
        image_bytes, mime_type = self._extract_inline_image(response)
        output_text = self._extract_response_text(response)
        if image_bytes:
            return image_bytes, mime_type, output_text

        raise RuntimeError(
            output_text.strip()
            or f"{model_name} returned no generated image."
        )

    @classmethod
    def _extract_interaction_image(cls, interaction) -> tuple[bytes, str]:
        output_image = getattr(interaction, "output_image", None)
        data = cls._read_value(output_image, "data")
        if not data:
            return b"", "image/jpeg"

        mime_type = (
            cls._read_value(output_image, "mime_type")
            or cls._read_value(output_image, "mimeType")
            or "image/jpeg"
        )
        return cls._decode_image_data(data), str(mime_type)

    @classmethod
    def _extract_response_text(cls, response) -> str:
        """Read text parts without relying on ``response.text``."""

        texts: list[str] = []
        direct_parts = getattr(response, "parts", None) or []
        for part in direct_parts:
            text = cls._read_value(part, "text")
            if text:
                texts.append(str(text))

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                text = cls._read_value(part, "text")
                if text:
                    texts.append(str(text))

        # Preserve order while removing duplicates.
        return "\n".join(dict.fromkeys(texts)).strip()

    @classmethod
    def _extract_inline_image(cls, response) -> tuple[bytes, str]:
        # Newer SDK versions expose response.parts directly.
        for part in getattr(response, "parts", None) or []:
            inline_data = getattr(part, "inline_data", None)
            data = cls._read_value(inline_data, "data")
            if data:
                mime_type = cls._read_value(inline_data, "mime_type") or "image/png"
                return cls._decode_image_data(data), str(mime_type)

        # Older/current SDK builds expose parts through candidates.
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                inline_data = getattr(part, "inline_data", None)
                data = cls._read_value(inline_data, "data")
                if not data:
                    continue
                mime_type = cls._read_value(inline_data, "mime_type") or "image/png"
                return cls._decode_image_data(data), str(mime_type)
        return b"", "image/png"

    @staticmethod
    def _read_value(value, key: str):
        if value is None:
            return None
        if isinstance(value, dict):
            return value.get(key)
        return getattr(value, key, None)

    @staticmethod
    def _decode_image_data(data) -> bytes:
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)
        if isinstance(data, str):
            return base64.b64decode(data)
        raise RuntimeError("Gemini returned an unreadable image payload.")

    @classmethod
    def _normalize_aspect_ratio(cls, value) -> str:
        normalized = str(value or "1:1").strip()
        if normalized not in cls.VALID_ASPECT_RATIOS:
            raise ValueError(
                "Unsupported aspect ratio. Use 1:1, 3:2, 2:3, 4:3, 3:4, "
                "4:5, 5:4, 16:9, 9:16, or 21:9."
            )
        return normalized

    @classmethod
    def _normalize_image_size(cls, value) -> str:
        normalized = str(value or "1K").strip().upper()
        if normalized in {"0.5K", "512", "512PX"}:
            normalized = "1K"
        if normalized not in cls.VALID_IMAGE_SIZES:
            raise ValueError("Unsupported image size. Use 1K, 2K, or 4K.")
        return normalized

    @classmethod
    def _error_blob(cls, error: Exception) -> str:
        """Return useful API diagnostics without exposing the API key."""

        values: list[str] = []
        for value in (str(error), repr(error)):
            value = str(value or "").strip()
            if value and value not in values:
                values.append(value)

        for name in (
            "message",
            "status",
            "code",
            "status_code",
            "details",
            "body",
            "response",
        ):
            try:
                value = getattr(error, name, None)
            except Exception:
                value = None
            if value is None:
                continue
            text = str(value).strip()
            if text and text not in values:
                values.append(text)

        return " | ".join(values)[:4000]

    @classmethod
    def _status_code(cls, error: Exception) -> int | None:
        for name in ("code", "status_code"):
            value = getattr(error, name, None)
            try:
                if value is not None:
                    return int(value)
            except (TypeError, ValueError):
                pass

        match = re.search(
            r"(?<!\d)(400|401|403|404|409|429|500|502|503|504)(?!\d)",
            cls._error_blob(error),
        )
        return int(match.group(1)) if match else None

    @classmethod
    def _requires_billing(cls, error: Exception) -> bool:
        text = cls._error_blob(error).lower()
        status = cls._status_code(error)
        billing_markers = (
            "free_tier",
            "free tier",
            "limit: 0",
            "limit=0",
            "billing required",
            "enable billing",
            "paid tier",
            "generate_content_free_tier",
        )
        return any(marker in text for marker in billing_markers) or (
            status == 429
            and "quota" in text
            and ("limit: 0" in text or "free tier" in text)
        )

    @classmethod
    def _looks_retryable(cls, error: Exception) -> bool:
        if cls._requires_billing(error):
            return False
        status = cls._status_code(error)
        if status in cls.RETRYABLE_STATUS_CODES:
            return True
        text = cls._error_blob(error).lower()
        return any(
            marker in text
            for marker in (
                "temporarily unavailable",
                "service unavailable",
                "timeout",
                "timed out",
                "connection",
                "rate limit",
            )
        )

    @classmethod
    def _friendly_error(cls, error: Exception) -> str:
        status = cls._status_code(error)
        text = cls._error_blob(error).lower()

        if cls._requires_billing(error):
            return (
                "Gemini image generation is not available on the free API "
                "tier. Enable billing for the Google AI project connected "
                "to GEMINI_API_KEY, or switch MV.ai to a local image model."
            )

        if status == 429:
            return (
                "The Gemini image-generation quota is exhausted. Check the "
                "API project's billing and rate limits, then try again later."
            )

        if status in cls.RETRYABLE_STATUS_CODES or cls._looks_retryable(error):
            return "Image generation is temporarily unavailable. Try again shortly."

        if status in {401, 403} or "api key" in text or "authentication" in text:
            if "permission" in text or "billing" in text or "denied" in text:
                return (
                    "This API key does not currently have access to Gemini "
                    "image generation. Check the key's Google AI project and billing."
                )
            return "Image generation authentication failed. Check GEMINI_API_KEY in .env."

        if status == 404 or "model not found" in text:
            return (
                "The configured Gemini image model is unavailable. Run "
                "INSTALL_IMAGE_GENERATION.bat to update google-genai."
            )

        if status == 400 or "invalid argument" in text:
            return (
                "Gemini rejected the image request configuration. The exact "
                "technical reason is printed in the terminal under "
                "[IMAGE API ERROR]."
            )

        if "safety" in text or "blocked" in text or "policy" in text:
            return "Gemini declined that image request because of its safety rules."

        if "interactions" in text and "attribute" in text:
            return (
                "Your google-genai package is too old for image generation. "
                "Run INSTALL_IMAGE_GENERATION.bat."
            )

        return (
            "Gemini image generation failed for a technical reason. Check the "
            "terminal line beginning with [IMAGE API ERROR] for the exact cause."
        )

