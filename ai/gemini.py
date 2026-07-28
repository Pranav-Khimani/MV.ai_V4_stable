import json
import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from ai.models import TaskPlan, TaskStep
from ai.prompts import SYSTEM_PROMPT
from ai.provider import AIProvider


load_dotenv()


class GeminiProvider(AIProvider):
    """
    Connects MV.AI to Gemini.

    Features:
    - Discovers models available to the API key.
    - Uses preferred models first.
    - Automatically switches models on quota limits,
      temporary server failures, or empty/invalid responses.
    - Converts Gemini JSON into TaskPlan objects.
    """

    PREFERRED_MODELS = [
        "gemini-3-flash-preview",
        "gemini-flash-latest",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]

    RETRYABLE_STATUS_CODES = {
    404,
    429,
    500,
    502,
    503,
    504,
}
    BLOCKED_MODEL_WORDS = (
        "embedding",
        "image",
        "imagen",
        "tts",
        "audio",
        "live",
        "veo",
        "robotics",
    )

    def __init__(self):
        self.client = None
        self.model_name = None
        self.available_models: list[str] = []
        self.initialization_error = None
        self.last_fallback_message = ""

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            self.initialization_error = (
                "GEMINI_API_KEY was not found in the .env file."
            )
            return

        try:
            self.client = genai.Client(
                api_key=api_key,
            )

            self.model_name = self.choose_model()

        except Exception as error:
            self.client = None
            self.model_name = None
            self.available_models = []

            self.initialization_error = (
                f"Could not initialize Gemini: {error}"
            )

    def choose_model(self) -> str:
        """
        Discover compatible models and build the fallback chain.
        """

        if self.client is None:
            raise RuntimeError(
                "Gemini client has not been initialized."
            )

        discovered_models: list[str] = []

        for model in self.client.models.list():
            model_name = getattr(
                model,
                "name",
                "",
            )

            if not model_name:
                continue

            model_name = model_name.removeprefix(
                "models/"
            )

            lowered_name = model_name.lower()

            if "gemini" not in lowered_name:
                continue

            if any(
                blocked_word in lowered_name
                for blocked_word in self.BLOCKED_MODEL_WORDS
            ):
                continue

            supported_actions = getattr(
                model,
                "supported_actions",
                None,
            )

            if supported_actions:
                normalized_actions = {
                    str(action).replace("_", "").lower()
                    for action in supported_actions
                }

                if "generatecontent" not in normalized_actions:
                    continue

            if model_name not in discovered_models:
                discovered_models.append(model_name)

        ordered_models: list[str] = []

        # Put preferred models first.
        for preferred_model in self.PREFERRED_MODELS:
            if (
                preferred_model in discovered_models
                and preferred_model not in ordered_models
            ):
                ordered_models.append(
                    preferred_model
                )

        # Add every other compatible Gemini model afterward.
        for model_name in sorted(discovered_models):
            if model_name not in ordered_models:
                ordered_models.append(model_name)

        self.available_models = ordered_models

        if not self.available_models:
            raise RuntimeError(
                "No compatible Gemini text model is available "
                "for this API key."
            )

        return self.available_models[0]

    def generate_plan(
        self,
        command: str,
    ) -> TaskPlan:
        """
        Convert a natural-language request into a TaskPlan.

        If one model reaches a rate limit or temporary failure,
        the next available model is tried automatically.
        """

        command = command.strip()

        if not command:
            return TaskPlan.empty(
                "Please enter a task."
            )

        if (
            self.client is None
            or self.model_name is None
            or not self.available_models
        ):
            return TaskPlan.empty(
                self.initialization_error
                or "Gemini is not available."
            )

        self.last_fallback_message = ""

        last_error = None
        attempted_models: list[str] = []

        # Start with the model that last succeeded.
        model_candidates = [
            self.model_name,
            *[
                model
                for model in self.available_models
                if model != self.model_name
            ],
        ]

        for model_name in model_candidates:
            attempted_models.append(model_name)

            try:
                response = (
                    self.client.models.generate_content(
                        model=model_name,
                        contents=command,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            temperature=0,
                            response_mime_type=(
                                "application/json"
                            ),
                        ),
                    )
                )

                response_text = getattr(
                    response,
                    "text",
                    None,
                )

                if not response_text:
                    last_error = RuntimeError(
                        f"{model_name} returned an empty response."
                    )

                    self.record_fallback(
                        model_name,
                        "empty response",
                    )

                    continue

                try:
                    raw_plan = json.loads(
                        response_text
                    )

                except json.JSONDecodeError as error:
                    last_error = error

                    self.record_fallback(
                        model_name,
                        "invalid JSON",
                    )

                    continue

                # Remember whichever model successfully responded.
                self.model_name = model_name

                return self.parse_task_plan(
                    raw_plan
                )

            except errors.APIError as error:
                last_error = error

                if self.is_retryable_error(error):
                    self.record_fallback(
                        model_name,
                        self.describe_error(error),
                    )

                    continue

                return TaskPlan.empty(
                    f"Gemini request failed using "
                    f"{model_name}: {error}"
                )

            except Exception as error:
                last_error = error

                if self.is_retryable_error(error):
                    self.record_fallback(
                        model_name,
                        self.describe_error(error),
                    )

                    continue

                return TaskPlan.empty(
                    f"Gemini request failed using "
                    f"{model_name}: {error}"
                )

        attempted_text = ", ".join(
            attempted_models
        )

        return TaskPlan.empty(
            "All available Gemini models failed.\n"
            f"Models tried: {attempted_text}\n"
            f"Last error: {last_error}"
        )

    def record_fallback(
        self,
        model_name: str,
        reason: str,
    ) -> None:
        """
        Save fallback information and print it for debugging.
        """

        message = (
            f"{model_name} failed because of {reason}. "
            "Trying the next model..."
        )

        self.last_fallback_message = message

        print(
            f"[Gemini fallback] {message}"
        )

    def is_retryable_error(
        self,
        error: Exception,
    ) -> bool:
        """
        Return True for errors where switching models may help.
        """

        status_code = getattr(
            error,
            "code",
            None,
        )

        if status_code in self.RETRYABLE_STATUS_CODES:
            return True

        error_text = str(error).lower()

        retryable_phrases = (
            "404",
            "not found",
            "no longer available",
            "newer model",
            "429",
            "resource_exhausted",
            "resource exhausted",
            "rate limit",
            "rate_limit",
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
        )

        return any(
            phrase in error_text
            for phrase in retryable_phrases
        )

    @staticmethod
    def describe_error(
        error: Exception,
    ) -> str:
        """
        Produce a short fallback reason.
        """

        status_code = getattr(
            error,
            "code",
            None,
        )

        if status_code == 429:
            return "a rate limit or quota limit"

        if status_code in {
            500,
            502,
            503,
            504,
        }:
            return (
                f"a temporary server error "
                f"({status_code})"
            )

        error_text = str(error)

        if len(error_text) > 150:
            error_text = (
                error_text[:147] + "..."
            )

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