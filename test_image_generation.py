from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from types import SimpleNamespace

from ai.planner import TaskPlanner
from core.assistant import Assistant
from core.executor import ExecutionReport, StepResult
from core.media_store import MediaStore
from tools.media.image_generation_tools import ImageGenerationTool


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZQmcAAAAASUVORK5CYII="
)


class FakeInteractions:
    def create(self, **_kwargs):
        return SimpleNamespace(
            output_image=SimpleNamespace(
                data=base64.b64encode(PNG_1X1).decode("ascii"),
                mime_type="image/png",
            ),
            output_text="",
        )


class FakeClient:
    def __init__(self):
        self.interactions = FakeInteractions()


def main() -> int:
    plan = TaskPlanner.try_create_direct_image_plan(
        "Generate an image of a minimal purple space city, landscape, 2K."
    )
    assert plan is not None
    step = plan.steps[0]
    assert step.tool == "images"
    assert step.args["action"] == "generate_image"
    assert step.args["aspect_ratio"] == "16:9"
    assert step.args["image_size"] == "2K"

    with tempfile.TemporaryDirectory() as temp_dir:
        tool = ImageGenerationTool.__new__(ImageGenerationTool)
        tool.client = FakeClient()
        tool.initialization_error = ""
        tool.media_store = MediaStore(root=Path(temp_dir) / "media")

        result = tool.execute(
            {
                "action": "generate_image",
                "prompt": "A minimal purple space city",
                "aspect_ratio": "16:9",
                "image_size": "1K",
            }
        )
        assert result["kind"] == "generated_image"
        assert Path(result["path"]).exists()
        assert result["display_text"] == "Your image is ready."

        report = ExecutionReport(
            goal="Generate an image",
            success=True,
            completed_steps=1,
            total_steps=1,
            results=[
                StepResult(
                    step_number=1,
                    description="Generate image",
                    tool="images",
                    action="generate_image",
                    success=True,
                    output=result,
                )
            ],
            message="",
        )
        assert Assistant.get_report_response_text(report) == "Your image is ready."
        attachments = Assistant.get_report_attachments(report)
        assert len(attachments) == 1
        assert attachments[0]["kind"] == "generated_image"

    print("[PASSED] Direct image-generation planning works.")
    print("[PASSED] Generated image bytes are saved as Reality attachments.")
    print("[PASSED] Structured image outputs are not printed as Python dictionaries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
