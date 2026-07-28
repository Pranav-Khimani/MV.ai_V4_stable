import json
import os
import time
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from ai.models import TaskPlan, TaskStep
from ai.prompts import SYSTEM_PROMPT
from ai.provider import AIProvider


load_dotenv()


class GeminiProvider(AIProvider):
    """Connect MV.ai to Gemini with retries and model fallback."""

    PREFERRED_MODELS = [
        "gemini-3-flash-preview",
        "gemini-flash-latest",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]

    RETRY_DELAYS_SECONDS = (0.0, 1.0, 2.0)
    TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
    SWITCH_MODEL_STATUS_CODES = {404}

    SERVICE_UNAVAILABLE_MESSAGE = (
        "Gemini is temporarily unavailable. Your local tools and profile "
        "still work. Try again shortly."
    )

    def __init__(self):
        self.client = None
        self.available_models = list(self.PREFERRED_MODELS)
        self.model_name = self.available_models[0]
        self.initialization_error: str | None = None
        self.last_fallback_message = ""

        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            self.model_name = None
            self.available_models = []
            self.initialization_error = (
                "Gemini is not configured. Add GEMINI_API_KEY to your "
                "local .env file. Your local tools and profile still work."
            )
            return

        try:
            # Creating the client is local. Do not list every model during
            # startup: that network call can return 503 and disable MV.ai
            # before the user even sends a command.
            self.client = genai.Client(api_key=api_key)
        except Exception as error:
            self.client = None
            self.model_name = None
            self.available_models = []
            self.initialization_error = self.friendly_error_message(error)
            print(f"[Gemini initialization error] {error}")

    def choose_model(self) -> str:
        """Return the current preferred model without a startup API call."""

        if not self.available_models:
            raise RuntimeError("No Gemini fallback models are configured.")
        return self.available_models[0]

    def generate_plan(self, command: str) -> TaskPlan:
        """Generate a plan, retrying transient errors before model fallback."""

        command = command.strip()
        if not command:
            return TaskPlan.empty("Please enter a task.")

        if self.client is None or not self.available_models:
            return TaskPlan.empty(
                self.initialization_error
                or self.SERVICE_UNAVAILABLE_MESSAGE
            )

        self.last_fallback_message = ""
        attempted_models: list[str] = []
        last_error: Exception | None = None

        model_candidates = [
            self.model_name,
            *[
                model
                for model in self.available_models
                if model != self.model_name
            ],
        ]
        model_candidates = [model for model in model_candidates if model]

        for model_name in model_candidates:
            attempted_models.append(model_name)

            for attempt_index, delay_seconds in enumerate(
                self.RETRY_DELAYS_SECONDS,
                start=1,
            ):
                if delay_seconds:
                    print(
                        f"[Gemini retry] Waiting {delay_seconds:.0f}s before "
                        f"attempt {attempt_index} with {model_name}."
                    )
                    time.sleep(delay_seconds)

                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=command,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            temperature=0,
                            response_mime_type="application/json",
                        ),
                    )

                    response_text = getattr(response, "text", None)
                    if not response_text:
                        raise RuntimeError(
                            f"{model_name} returned an empty response."
                        )

                    try:
                        raw_plan = json.loads(response_text)
                    except json.JSONDecodeError as error:
                        raise RuntimeError(
                            f"{model_name} returned invalid JSON."
                        ) from error

                    self.model_name = model_name
                    return self.parse_task_plan(raw_plan)

                except errors.APIError as error:
                    last_error = error
                    status_code = self.get_status_code(error)

                    if status_code in self.SWITCH_MODEL_STATUS_CODES:
                        self.record_fallback(
                            model_name,
                            self.describe_error(error),
                        )
                        break

                    if self.is_retryable_error(error):
                        if attempt_index < len(self.RETRY_DELAYS_SECONDS):
                            self.record_retry(
                                model_name,
                                attempt_index,
                                self.describe_error(error),
                            )
                            continue

                        self.record_fallback(
                            model_name,
                            self.describe_error(error),
                        )
                        break

                    print(f"[Gemini request error] {model_name}: {error}")
                    return TaskPlan.empty(
                        self.friendly_error_message(error)
                    )

                except Exception as error:
                    last_error = error

                    if self.is_retryable_error(error):
                        if attempt_index < len(self.RETRY_DELAYS_SECONDS):
                            self.record_retry(
                                model_name,
                                attempt_index,
                                self.describe_error(error),
                            )
                            continue

                        self.record_fallback(
                            model_name,
                            self.describe_error(error),
                        )
                        break

                    # Empty or malformed responses can be model-specific, so
                    # switch models after the retry sequence.
                    error_text = str(error).lower()
                    if "empty response" in error_text or "invalid json" in error_text:
                        if attempt_index < len(self.RETRY_DELAYS_SECONDS):
                            self.record_retry(
                                model_name,
                                attempt_index,
                                self.describe_error(error),
                            )
                            continue
                        self.record_fallback(
                            model_name,
                            self.describe_error(error),
                        )
                        break

                    print(f"[Gemini request error] {model_name}: {error}")
                    return TaskPlan.empty(
                        self.friendly_error_message(error)
                    )

        print(
            "[Gemini unavailable] Models tried: "
            + ", ".join(attempted_models)
        )
        if last_error is not None:
            print(f"[Gemini unavailable] Last error: {last_error}")

        return TaskPlan.empty(self.SERVICE_UNAVAILABLE_MESSAGE)

    def record_retry(
        self,
        model_name: str,
        attempt_number: int,
        reason: str,
    ) -> None:
        next_delay = self.RETRY_DELAYS_SECONDS[attempt_number]
        print(
            f"[Gemini retry] {model_name} failed because of {reason}. "
            f"Retrying in {next_delay:.0f}s..."
        )

    def record_fallback(self, model_name: str, reason: str) -> None:
        message = (
            f"{model_name} failed because of {reason}. "
            "Trying the next model..."
        )
        self.last_fallback_message = message
        print(f"[Gemini fallback] {message}")

    @classmethod
    def get_status_code(cls, error: Exception) -> int | None:
        code = getattr(error, "code", None)
        try:
            return int(code) if code is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def is_retryable_error(cls, error: Exception) -> bool:
        status_code = cls.get_status_code(error)
        if status_code in cls.TRANSIENT_STATUS_CODES:
            return True

        error_text = str(error).lower()
        retryable_phrases = (
            "429",
            "resource_exhausted",
            "resource exhausted",
            "rate limit",
            "quota",
            "too many requests",
            "500",
            "502",
            "503",
            "504",
            "server error",
            "service unavailable",
            "temporarily unavailable",
            "deadline exceeded",
            "timeout",
            "timed out",
            "connection error",
            "connection reset",
            "connection aborted",
        )
        return any(phrase in error_text for phrase in retryable_phrases)

    @classmethod
    def friendly_error_message(cls, error: Exception) -> str:
        status_code = cls.get_status_code(error)
        error_text = str(error).lower()

        if status_code in cls.TRANSIENT_STATUS_CODES or cls.is_retryable_error(error):
            return cls.SERVICE_UNAVAILABLE_MESSAGE

        if status_code in {401, 403} or any(
            phrase in error_text
            for phrase in (
                "api key not valid",
                "invalid api key",
                "permission denied",
                "unauthenticated",
            )
        ):
            return (
                "Gemini authentication failed. Check GEMINI_API_KEY in your "
                "local .env file. Your local tools and profile still work."
            )

        return (
            "Gemini could not complete that request. Your local tools and "
            "profile still work. Try again shortly."
        )

    @classmethod
    def describe_error(cls, error: Exception) -> str:
        status_code = cls.get_status_code(error)

        if status_code == 429:
            return "a rate limit or quota limit"
        if status_code in {500, 502, 503, 504}:
            return f"a temporary server error ({status_code})"
        if status_code == 404:
            return "the model is unavailable (404)"

        error_text = str(error).strip() or error.__class__.__name__
        if len(error_text) > 150:
            error_text = error_text[:147] + "..."
        return error_text

    def parse_task_plan(
        self,
        raw_plan: Any,
    ) -> TaskPlan:
        """
        Validate the basic response structure and build
        TaskPlan objects.
        """

        if not isinstance(raw_plan, dict):
            return TaskPlan.empty(
                "Gemini returned an invalid task plan."
            )

        goal = raw_plan.get(
            "goal",
            "",
        )

        message = raw_plan.get(
            "message",
            "",
        )

        raw_steps = raw_plan.get(
            "steps",
            [],
        )

        if not isinstance(goal, str):
            goal = str(goal)

        if not isinstance(message, str):
            message = str(message)

        if not isinstance(raw_steps, list):
            return TaskPlan.empty(
                "Gemini returned an invalid steps list."
            )

        steps: list[TaskStep] = []

        for index, raw_step in enumerate(
            raw_steps,
            start=1,
        ):
            parsed_step = self.parse_task_step(
                raw_step,
                index,
            )

            if isinstance(parsed_step, str):
                return TaskPlan.empty(
                    parsed_step
                )

            steps.append(parsed_step)

        return TaskPlan(
            goal=goal.strip(),
            steps=steps,
            message=message.strip(),
        )

    def parse_task_step(
        self,
        raw_step: Any,
        step_number: int,
    ) -> TaskStep | str:
        """
        Validate and convert one JSON step into a TaskStep.
        """

        if not isinstance(raw_step, dict):
            return (
                f"Step {step_number} is not "
                "a valid object."
            )

        device = raw_step.get("device")
        tool = raw_step.get("tool")
        args = raw_step.get(
            "args",
            {},
        )
        description = raw_step.get(
            "description",
            "",
        )

        if (
            not isinstance(device, str)
            or not device.strip()
        ):
            return (
                f"Step {step_number} has "
                "no valid device."
            )

        if (
            not isinstance(tool, str)
            or not tool.strip()
        ):
            return (
                f"Step {step_number} has "
                "no valid tool."
            )

        if not isinstance(args, dict):
            return (
                f"Step {step_number} has "
                "invalid arguments."
            )

        if not isinstance(description, str):
            description = str(description)

        return TaskStep(
            device=device.strip().lower(),
            tool=tool.strip().lower(),
            args=args,
            description=description.strip(),
        )

    def is_ready(self) -> bool:
        return (
            self.client is not None
            and self.model_name is not None
            and bool(self.available_models)
        )

    def get_status(self) -> str:
        if self.is_ready():
            model_position = (
                self.available_models.index(
                    self.model_name
                )
                + 1
            )

            return (
                f"Gemini ready: {self.model_name} "
                f"({model_position}/"
                f"{len(self.available_models)} models)"
            )

        return (
            self.initialization_error
            or "Gemini is unavailable."
        )

    def get_available_models(
        self,
    ) -> list[str]:
        """
        Return a safe copy of the model fallback chain.
        """

        return list(self.available_models)