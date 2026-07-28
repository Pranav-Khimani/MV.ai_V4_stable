from __future__ import annotations

import mimetypes
import shutil
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.app_paths import get_app_data_dir


@dataclass(frozen=True)
class ImageAttachment:
    """Metadata for one image copied into MV.ai's private media folder."""

    kind: str
    path: str
    relative_path: str
    original_name: str
    stored_name: str
    mime_type: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MediaStore:
    """Validate and persist user-selected images outside the source folder."""

    SUPPORTED_EXTENSIONS = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    # Gemini inline requests must stay below 20 MB including the prompt.
    MAX_IMAGE_BYTES = 18 * 1024 * 1024

    def __init__(self, root: Path | None = None):
        self.app_root = get_app_data_dir()
        self.root = Path(root) if root is not None else self.app_root / "media"
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def inspect_image(cls, source: str | Path) -> dict[str, Any]:
        path = Path(source).expanduser().resolve()

        if not path.exists() or not path.is_file():
            raise ValueError("The selected image no longer exists.")

        extension = path.suffix.lower()
        expected_mime = cls.SUPPORTED_EXTENSIONS.get(extension)
        if expected_mime is None:
            raise ValueError("Use a PNG, JPG, JPEG, or WebP image.")

        size_bytes = path.stat().st_size
        if size_bytes <= 0:
            raise ValueError("The selected image is empty.")
        if size_bytes > cls.MAX_IMAGE_BYTES:
            raise ValueError(
                "That image is too large. Choose an image smaller than 18 MB."
            )

        with path.open("rb") as file:
            header = file.read(16)

        detected_mime = cls._detect_mime(header)
        if detected_mime is None:
            raise ValueError("MV.ai could not verify that this is a valid image.")
        if detected_mime != expected_mime:
            raise ValueError(
                "The file extension does not match the image data. "
                "Re-save the image as PNG, JPG, or WebP and try again."
            )

        return {
            "path": path,
            "mime_type": detected_mime,
            "size_bytes": size_bytes,
            "original_name": path.name,
        }

    @staticmethod
    def _detect_mime(header: bytes) -> str | None:
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if header.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
            return "image/webp"
        return None

    def store_image(self, source: str | Path) -> ImageAttachment:
        details = self.inspect_image(source)
        source_path: Path = details["path"]

        now = datetime.now()
        destination_dir = self.root / now.strftime("%Y") / now.strftime("%m")
        destination_dir.mkdir(parents=True, exist_ok=True)

        canonical_extension = mimetypes.guess_extension(details["mime_type"]) or source_path.suffix.lower()
        if canonical_extension == ".jpe":
            canonical_extension = ".jpg"

        stored_name = f"{uuid.uuid4().hex}{canonical_extension}"
        destination = destination_dir / stored_name
        shutil.copy2(source_path, destination)

        relative_path = destination.relative_to(self.app_root)
        return ImageAttachment(
            kind="image",
            path=str(destination),
            relative_path=str(relative_path),
            original_name=source_path.name,
            stored_name=stored_name,
            mime_type=details["mime_type"],
            size_bytes=details["size_bytes"],
        )

    def resolve_path(self, attachment: dict[str, Any] | ImageAttachment) -> Path | None:
        data = attachment.to_dict() if isinstance(attachment, ImageAttachment) else attachment

        absolute = Path(str(data.get("path", ""))).expanduser()
        if str(absolute) and absolute.exists():
            return absolute.resolve()

        relative = str(data.get("relative_path", "")).strip()
        if relative:
            candidate = self.app_root / relative
            if candidate.exists():
                return candidate.resolve()

        return None
