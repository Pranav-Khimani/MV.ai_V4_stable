from __future__ import annotations

import base64
from types import SimpleNamespace

from tools.media.image_generation_tools import ImageGenerationTool


PNG_BYTES = b"\x89PNG\r\n\x1a\ncompat-test"


class FakeModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        inline = SimpleNamespace(data=base64.b64encode(PNG_BYTES).decode(), mime_type="image/png")
        part = SimpleNamespace(inline_data=inline, text=None)
        return SimpleNamespace(parts=[part], candidates=[])


class FakeClient:
    def __init__(self):
        self.models = FakeModels()
        self.interactions = None


def main() -> int:
    tool = ImageGenerationTool.__new__(ImageGenerationTool)
    tool.client = FakeClient()
    data, mime, text = tool._generate_with_model(
        model_name="gemini-3.1-flash-image",
        prompt="Generate an image of a cute cat",
        aspect_ratio="1:1",
        image_size="1K",
    )
    assert data == PNG_BYTES
    assert mime == "image/png"
    assert text == ""
    call = tool.client.models.calls[0]
    assert call["contents"] == ["Generate an image of a cute cat"]
    assert "config" not in call
    print("[PASSED] Default image generation uses compatibility-safe request.")
    print("[PASSED] Direct response.parts image extraction works.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
