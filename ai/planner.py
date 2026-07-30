import re
from typing import Any

from ai.models import TaskPlan, TaskStep
from ai.provider import AIProvider
from core.registry import ToolRegistry


class TaskPlanner:
    """
    Creates and validates multi-step task plans for MV.AI.

    The AI provider creates a proposed plan.
    This class checks that every device, tool, action,
    and argument is valid before execution.
    """


    MAX_STEPS = 20

    def __init__(
        self,
        provider: AIProvider,
        registry: ToolRegistry | None = None,
    ):
        self.provider = provider
        self.registry = registry or self._discover_registry()

    @staticmethod
    def _discover_registry() -> ToolRegistry:
        """Build a schema registry for standalone planner tests."""

        from core.plugin_loader import discover_tools

        registry = ToolRegistry()
        tools, errors = discover_tools()

        for tool in tools:
            registry.register(tool)

        if errors:
            raise RuntimeError(
                "Could not load tool schemas: " + "; ".join(errors)
            )

        return registry

    def create_plan(
        self,
        command: str,
        memory_context: str = "",
        conversation_context: str = "",
    ) -> TaskPlan:
        """
        Ask the provider to create a plan using the user's
        command, long-term memory, and recent conversation.
        """

        command = command.strip()

        if not command:
            return TaskPlan.empty(
                "Please enter a task."
            )

        # Screenshot requests are deterministic local desktop actions.
        # Route them locally so Gemini cannot mistake them for chat.
        direct_screenshot_plan = self.try_create_direct_screenshot_plan(
            command
        )

        if direct_screenshot_plan is not None:
            return self.validate_plan(direct_screenshot_plan)

        # Common image-generation requests are parsed locally only when
        # the feature is registered. When disabled, Assistant returns a clean
        # local message before Gemini or the planner is called.
        if self.registry.get("images") is not None:
            direct_image_plan = self.try_create_direct_image_plan(command)
            if direct_image_plan is not None:
                return self.validate_plan(direct_image_plan)

        # Complete email commands are parsed locally before Gemini.
        # This prevents the planner from shrinking a topic into a few
        # keywords or accidentally using the subject as the message.
        direct_email_plan = self.try_create_direct_email_plan(
            command
        )

        if direct_email_plan is not None:
            return self.validate_plan(
                direct_email_plan
            )

        enriched_command = self.build_contextual_command(
            command=command,
            memory_context=memory_context,
            conversation_context=conversation_context,
        )

        try:
            proposed_plan = self.provider.generate_plan(
                enriched_command
            )

        except Exception as error:
            print(f"[AI planner error] {error}")
            return TaskPlan.empty(
                "Gemini is temporarily unavailable. Your local tools and "
                "profile still work. Try again shortly."
            )

        return self.validate_plan(
            proposed_plan
        )

    @classmethod
    def try_create_direct_screenshot_plan(
        cls,
        command: str,
    ) -> TaskPlan | None:
        """Create a reliable local plan for screenshot commands."""

        normalized = " ".join(str(command).strip().lower().split())
        if not normalized:
            return None

        open_folder_patterns = (
            r"\bopen (?:my |the )?screenshots? folder\b",
            r"\bshow (?:my |the )?screenshots? folder\b",
            r"\bwhere are (?:my )?screenshots?\b",
        )
        if any(re.search(pattern, normalized) for pattern in open_folder_patterns):
            return TaskPlan(
                goal="Open the screenshots folder",
                steps=[
                    TaskStep(
                        device="laptop",
                        tool="screenshot",
                        args={"action": "open_folder"},
                        description="Open the MV.AI screenshots folder.",
                    )
                ],
                message="",
            )

        capture_patterns = (
            r"\btake (?:a )?screenshots?\b",
            r"\bcapture (?:my |the )?(?:screen|desktop)\b",
            r"\bscreenshot (?:my |the )?(?:screen|desktop)\b",
            r"\bscreen ?shot\b",
        )
        if not any(re.search(pattern, normalized) for pattern in capture_patterns):
            return None

        open_after_capture = not bool(
            re.search(r"\b(?:do not|don't|dont) open\b", normalized)
        )

        return TaskPlan(
            goal="Take a screenshot",
            steps=[
                TaskStep(
                    device="laptop",
                    tool="screenshot",
                    args={
                        "action": "capture",
                        "open_after_capture": open_after_capture,
                    },
                    description="Capture and save the desktop screenshot.",
                )
            ],
            message="",
        )

    @staticmethod
    def is_image_generation_request(command: str) -> bool:
        """Return True for clear requests to create a new visual."""

        normalized = " ".join(str(command).strip().split())
        if not normalized:
            return False

        intent = re.search(
            r"\b(?:generate|create|make|draw|design|render|produce)\b",
            normalized,
            flags=re.IGNORECASE,
        )
        visual = re.search(
            r"\b(?:image|picture|photo|poster|wallpaper|illustration|"
            r"artwork|visual|logo|icon|portrait)\b",
            normalized,
            flags=re.IGNORECASE,
        )
        return bool(intent and visual)

    @classmethod
    def try_create_direct_image_plan(
        cls,
        command: str,
    ) -> TaskPlan | None:
        """Create a reliable single-step plan for clear generation requests."""

        normalized = " ".join(command.strip().split())
        if not cls.is_image_generation_request(normalized):
            return None

        intent = re.search(
            r"\b(?:generate|create|make|draw|design|render)\b",
            normalized,
            flags=re.IGNORECASE,
        )
        visual = re.search(
            r"\b(?:image|picture|photo|poster|wallpaper|illustration|artwork|visual|logo)\b",
            normalized,
            flags=re.IGNORECASE,
        )
        if not intent or not visual:
            return None

        prompt = normalized[intent.end():].strip(" ,:-")
        prompt = re.sub(
            r"^(?:me\s+)?(?:an?|the)\s+",
            "",
            prompt,
            count=1,
            flags=re.IGNORECASE,
        ).strip()
        if not prompt:
            return None

        aspect_ratio = "1:1"
        ratio_match = re.search(r"\b(21:9|16:9|9:16|5:4|4:5|4:3|3:4|3:2|2:3|1:1)\b", normalized)
        if ratio_match:
            aspect_ratio = ratio_match.group(1)
        elif re.search(r"\bportrait\b", normalized, re.IGNORECASE):
            aspect_ratio = "9:16"
        elif re.search(r"\blandscape|widescreen\b", normalized, re.IGNORECASE):
            aspect_ratio = "16:9"
        elif re.search(r"\bsquare\b", normalized, re.IGNORECASE):
            aspect_ratio = "1:1"

        size_match = re.search(r"\b(1K|2K|4K)\b", normalized, re.IGNORECASE)
        image_size = size_match.group(1).upper() if size_match else "1K"

        return TaskPlan(
            goal="Generate an image",
            steps=[
                TaskStep(
                    device="laptop",
                    tool="images",
                    args={
                        "action": "generate_image",
                        "prompt": prompt,
                        "aspect_ratio": aspect_ratio,
                        "image_size": image_size,
                    },
                    description="Generate and save the requested image.",
                )
            ],
            message="",
        )

    @classmethod
    def try_create_direct_email_plan(
        cls,
        command: str,
    ) -> TaskPlan | None:
        """
        Parse a complete send-email command without asking Gemini.

        Two message styles are deliberately different:
        - "saying ..." preserves the user's exact message.
        - "about/regarding ..." creates a complete short email body.

        Incomplete or unusual email requests fall back to the AI planner,
        which can ask a follow-up question using conversation context.
        """

        contains_email = bool(
            re.search(
                r"\bemail\b",
                command,
                flags=re.IGNORECASE,
            )
        )
        has_email_intent = bool(
            re.search(
                r"\b(?:send|write|compose)\b",
                command,
                flags=re.IGNORECASE,
            )
        ) or command.strip().lower().startswith("email ")

        if not contains_email or not has_email_intent:
            return None

        recipient_match = re.search(
            r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}",
            command,
            flags=re.IGNORECASE,
        )

        if recipient_match is None:
            return None

        recipient = recipient_match.group(0).strip()
        subject = cls.extract_email_subject(command)

        if not subject:
            return None

        exact_body = cls.extract_exact_email_body(command)

        if exact_body:
            body = exact_body
            body_mode = "exact"
        else:
            topic = cls.extract_email_topic(command)

            if not topic:
                return None

            body = cls.compose_topic_email(topic)
            body_mode = "composed"

        return TaskPlan(
            goal=f"Send an email to {recipient}",
            steps=[
                TaskStep(
                    device="laptop",
                    tool="email",
                    args={
                        "action": "send_email",
                        "to": recipient,
                        "subject": subject,
                        "body": body,
                        "body_mode": body_mode,
                    },
                    description=(
                        f"Review and send an email to {recipient}"
                    ),
                )
            ],
            message="",
        )

    @classmethod
    def extract_email_subject(
        cls,
        command: str,
    ) -> str:
        """Extract a subject/title clause from the user command."""

        patterns = (
            r"(?:,|\s)\s*(?:with\s+)?(?:the\s+)?"
            r"(?:subject|title)(?:\s+(?:is|named|called))?"
            r"\s*[:=\-]?\s*(.+?)\s*[.!?]*$",
            r"\b(?:subject|title)\s*[:=\-]\s*(.+?)\s*[.!?]*$",
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                command,
                flags=re.IGNORECASE | re.DOTALL,
            )

            if match:
                return cls.clean_email_fragment(
                    match.group(1)
                )

        return ""

    @classmethod
    def extract_exact_email_body(
        cls,
        command: str,
    ) -> str:
        """Extract text the user explicitly asked to send verbatim."""

        subject_boundary = (
            r"(?=\s*,?\s*(?:with\s+)?(?:the\s+)?"
            r"(?:subject|title)\b|$)"
        )
        patterns = (
            r"\bsaying\s*[:=\-]?\s*(.+?)" + subject_boundary,
            r"\b(?:with\s+)?(?:the\s+)?message"
            r"(?:\s+(?:is|saying))?\s*[:=\-]?\s*(.+?)"
            + subject_boundary,
            r"\b(?:with\s+)?(?:the\s+)?body"
            r"(?:\s+is)?\s*[:=\-]?\s*(.+?)"
            + subject_boundary,
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                command,
                flags=re.IGNORECASE | re.DOTALL,
            )

            if match:
                return cls.clean_email_fragment(
                    match.group(1),
                    preserve_terminal_punctuation=True,
                )

        return ""

    @classmethod
    def extract_email_topic(
        cls,
        command: str,
    ) -> str:
        """Extract a topic that should be expanded into an email body."""

        subject_boundary = (
            r"(?=\s*,?\s*(?:with\s+)?(?:the\s+)?"
            r"(?:subject|title)\b|$)"
        )
        patterns = (
            r"\babout\s+(.+?)" + subject_boundary,
            r"\bregarding\s+(.+?)" + subject_boundary,
            r"\bon\s+the\s+topic\s+of\s+(.+?)" + subject_boundary,
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                command,
                flags=re.IGNORECASE | re.DOTALL,
            )

            if match:
                return cls.clean_email_fragment(
                    match.group(1)
                )

        return ""

    @staticmethod
    def clean_email_fragment(
        value: str,
        preserve_terminal_punctuation: bool = False,
    ) -> str:
        """Normalize surrounding quotes and command punctuation."""

        cleaned = " ".join(str(value).strip().split())
        cleaned = cleaned.strip(" \t\r\n\"'`.,;:-")

        if preserve_terminal_punctuation:
            original = " ".join(str(value).strip().split())
            terminal = original[-1:] if original else ""

            if terminal in ".!?" and not cleaned.endswith(terminal):
                cleaned += terminal

        return cleaned

    @classmethod
    def compose_topic_email(
        cls,
        topic: str,
    ) -> str:
        """Turn a topic phrase into a complete, readable email."""

        topic = cls.clean_email_fragment(topic)

        if not topic:
            return ""

        main_topic = topic
        extra_detail = ""

        split_match = re.match(
            r"(.+?)\s+(?:and|also)\s+"
            r"((?:this|it|i|we|please|the)\b.+)",
            topic,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if split_match:
            main_topic = cls.clean_email_fragment(
                split_match.group(1)
            )
            extra_detail = cls.clean_email_fragment(
                split_match.group(2)
            )

        opening = f"I'm writing about {main_topic}."
        sentences = ["Hi,", "", opening]

        if extra_detail:
            detail = extra_detail[0].upper() + extra_detail[1:]

            if detail[-1:] not in ".!?":
                detail += "."

            sentences[-1] = f"{sentences[-1]} {detail}"

        sentences.extend(
            [
                "",
                "Best regards,",
            ]
        )

        return "\n".join(sentences)

    @staticmethod
    def build_contextual_command(
        command: str,
        memory_context: str = "",
        conversation_context: str = "",
    ) -> str:
        """
        Build the full request supplied to the AI provider.
        """

        memory_context = memory_context.strip()
        conversation_context = conversation_context.strip()

        if not memory_context:
            memory_context = (
                "No long-term memories are available."
            )

        if not conversation_context:
            conversation_context = (
                "No recent conversation is available."
            )

        return f"""
CONTEXT FOR MV.AI

The following information is trusted context stored by
the assistant. Use it only when it is relevant to the
user's current request.

LONG-TERM MEMORY:
{memory_context}

RECENT CONVERSATION:
{conversation_context}

CURRENT USER REQUEST:
{command}

INSTRUCTIONS:
- Use stored context to understand references such as
  "my project", "my folder", "my editor", or "it".
- Do not mention the memory context unless it helps answer
  the request.
- Never invent a stored fact that is not present above.
- For a normal question that requires no tool, return zero
  steps and place the answer in the plan's message field.
- For an executable request, return the required validated
  tool steps.
""".strip()

    def validate_plan(self, plan: Any) -> TaskPlan:
        """
        Validate an entire TaskPlan.
        """

        if not isinstance(plan, TaskPlan):
            return TaskPlan.empty(
                "The AI provider returned an invalid plan object."
            )

        if not isinstance(plan.goal, str):
            return TaskPlan.empty(
                "The task goal is invalid."
            )

        if not isinstance(plan.message, str):
            return TaskPlan.empty(
                "The task message is invalid."
            )

        if not isinstance(plan.steps, list):
            return TaskPlan.empty(
                "The task steps are invalid."
            )

        if len(plan.steps) > self.MAX_STEPS:
            return TaskPlan.empty(
                f"The plan contains too many steps. "
                f"The maximum is {self.MAX_STEPS}."
            )

        validated_steps: list[TaskStep] = []

        for step_number, step in enumerate(
            plan.steps,
            start=1,
        ):
            error = self.validate_step(
                step,
                step_number,
            )

            if error:
                return TaskPlan.empty(error)

            validated_steps.append(
                self.clean_step(step)
            )

        return TaskPlan(
            goal=plan.goal.strip(),
            steps=validated_steps,
            message=plan.message.strip(),
        )

    def validate_step(
        self,
        step: Any,
        step_number: int,
    ) -> str | None:
        """
        Validate one task step.

        Returns:
            None when valid.
            An error message when invalid.
        """

        if not isinstance(step, TaskStep):
            return (
                f"Step {step_number} is not a valid TaskStep."
            )

        device = step.device.strip().lower()
        tool = step.tool.strip().lower()

        if device not in self.registry.supported_devices():
            return (
                f"Step {step_number} uses unsupported "
                f"device '{step.device}'."
            )

        if not tool:
            return (
                f"Step {step_number} has no tool."
            )

        if not isinstance(step.args, dict):
            return (
                f"Step {step_number} has invalid arguments."
            )

        action = step.args.get("action")

        if not isinstance(action, str) or not action.strip():
            return (
                f"Step {step_number} has no valid action."
            )

        action = action.strip().lower()

        tool_schema = self.registry.get_schema(tool)
        if tool_schema is None:
            return (
                f"Step {step_number} uses unknown "
                f"tool '{step.tool}'."
            )

        device_error = self.validate_device_tool(
            device=device,
            tool=tool,
            step_number=step_number,
        )

        if device_error:
            return device_error

        if self.registry.get_action_schema(tool, action) is None:
            return (
                f"Step {step_number} uses unsupported "
                f"action '{action}' for tool '{tool}'."
            )

        required_error = self.validate_required_arguments(
            tool=tool,
            action=action,
            args=step.args,
            step_number=step_number,
        )

        if required_error:
            return required_error

        value_error = self.validate_argument_values(
            tool=tool,
            action=action,
            args=step.args,
            step_number=step_number,
        )

        if value_error:
            return value_error

        return None

    def validate_device_tool(
        self,
        device: str,
        tool: str,
        step_number: int,
    ) -> str | None:
        """Ensure the tool schema supports the selected device."""

        if self.registry.supports_device(tool, device):
            return None

        if device == "phone" and "phone" not in self.registry.supported_devices():
            return (
                f"Step {step_number} requires phone tool '{tool}', "
                "but no phone tools are implemented yet."
            )

        return (
            f"Step {step_number} uses tool '{tool}', which is not "
            f"available on the {device}."
        )

    def validate_required_arguments(
        self,
        tool: str,
        action: str,
        args: dict[str, Any],
        step_number: int,
    ) -> str | None:
        """
        Ensure required arguments exist and are not empty.
        """

        action_schema = self.registry.get_action_schema(
            tool,
            action,
        )
        required_arguments = (
            action_schema.required_arguments
            if action_schema is not None
            else ()
        )

        for argument_name in required_arguments:
            if argument_name not in args:
                return (
                    f"Step {step_number} is missing "
                    f"required argument "
                    f"'{argument_name}'."
                )

            argument_value = args[argument_name]

            if argument_value is None:
                return (
                    f"Step {step_number} has an empty "
                    f"'{argument_name}' argument."
                )

            if (
                isinstance(argument_value, str)
                and not argument_value.strip()
            ):
                return (
                    f"Step {step_number} has an empty "
                    f"'{argument_name}' argument."
                )

        return None

    def validate_argument_values(
        self,
        tool: str,
        action: str,
        args: dict[str, Any],
        step_number: int,
    ) -> str | None:
        """
        Validate special argument types and ranges.
        """

        if (
            tool == "device"
            and action in {
                "set_volume",
                "set_brightness",
            }
        ):
            level = args.get("level")

            if isinstance(level, bool):
                return (
                    f"Step {step_number} has an invalid "
                    f"level value."
                )

            if not isinstance(level, (int, float)):
                return (
                    f"Step {step_number} requires a "
                    f"numeric level."
                )

            if not 0 <= level <= 100:
                return (
                    f"Step {step_number} requires a "
                    f"level from 0 to 100."
                )

        return None

    def clean_step(
        self,
        step: TaskStep,
    ) -> TaskStep:
        """
        Return a normalized copy of a validated step.
        """

        cleaned_args = dict(step.args)

        action = cleaned_args.get("action")

        if isinstance(action, str):
            cleaned_args["action"] = (
                action.strip().lower()
            )

        if (
            cleaned_args.get("action")
            in {
                "set_volume",
                "set_brightness",
            }
        ):
            level = cleaned_args.get("level")

            if isinstance(level, float):
                cleaned_args["level"] = round(level)

        return TaskStep(
            device=step.device.strip().lower(),
            tool=step.tool.strip().lower(),
            args=cleaned_args,
            description=step.description.strip(),
        )

    def get_status(self) -> str:
        """
        Return the AI provider's status when supported.
        """

        status_method = getattr(
            self.provider,
            "get_status",
            None,
        )

        if callable(status_method):
            return status_method()

        return "AI provider configured."