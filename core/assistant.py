from ai.gemini import GeminiProvider
from ai.planner import TaskPlanner
from ai.prompts import build_system_prompt

from core.app_paths import get_memory_database_path, get_project_root
from core.media_store import MediaStore
from core.executor import ExecutionReport, TaskExecutor
from core.permissions import PermissionManager
from core.plugin_loader import discover_tools
from core.registry import ToolRegistry
from core.task_manager import CancellationToken

from memory.memory_manager import MemoryManager
from memory.reality_manager import RealityManager
from memory.user_profile import UserProfile


class Assistant:
    """
    Main controller for MV.AI.

    Responsibilities:
    - Load tool plugins.
    - Convert natural-language commands into task plans.
    - Supply memory and conversation context to Gemini.
    - Execute validated task-plan steps.
    - Store conversations and command history.
    """

    def __init__(self):
        self.registry = ToolRegistry()
        self.plugin_errors: list[str] = []

        self.load_tools()

        self.permission_manager = PermissionManager(self.registry)
        system_prompt = build_system_prompt(
            self.registry.list_schemas()
        )
        self.ai_provider = GeminiProvider(
            system_prompt=system_prompt
        )
        self.planner = TaskPlanner(
            self.ai_provider,
            self.registry,
        )

        self.executor = TaskExecutor(
            registry=self.registry,
            permission_manager=self.permission_manager,
        )

        database_path = get_memory_database_path()

        self.memory = MemoryManager(
            database_path=str(database_path)
        )
        self.realities = RealityManager(
            self.memory
        )

        profile_path = get_project_root() / "user_profile.json"
        self.user_profile = UserProfile(profile_path)
        self.media_store = MediaStore()

        print(f"[Memory database] {database_path}")
        print(f"[Editable user profile] {profile_path}")

    def load_tools(self) -> None:
        """
        Discover and register every tool plugin.
        """

        discovered_tools, loading_errors = discover_tools()
        self.plugin_errors.extend(loading_errors)

        for tool in discovered_tools:
            try:
                self.registry.register(tool)
            except Exception as error:
                self.plugin_errors.append(
                    f"Could not register "
                    f"{tool.__class__.__name__}: {error}"
                )

        # Email is a flagship capability. Keep a direct fallback so a
        # packaging/discovery problem cannot silently remove it.
        if self.registry.get("email") is None:
            try:
                from tools.communication.email_tools import EmailTool

                self.registry.register(
                    EmailTool()
                )
            except Exception as error:
                self.plugin_errors.append(
                    f"Could not register EmailTool fallback: {error}"
                )

        print(
            "[Registered tools] "
            + ", ".join(
                self.registry.list_tools()
            )
        )

        if self.plugin_errors:
            print("[Plugin warnings]")
            for error in self.plugin_errors:
                print(f"- {error}")

    def handle_command(
        self,
        command: str,
        confirmation_callback=None,
        progress_callback=None,
        cancellation_token: CancellationToken | None = None,
        stage_callback=None,
    ) -> ExecutionReport:
        """
        Process one user command from beginning to end.
        """

        command = command.strip()

        def stage(
            name: str,
            current: int = 0,
            total: int = 0,
            detail=None,
        ) -> None:
            if callable(stage_callback):
                stage_callback(
                    name,
                    current,
                    total,
                    detail,
                )

        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

        if not command:
            return ExecutionReport(
                goal="",
                success=False,
                completed_steps=0,
                total_steps=0,
                message="Please enter a task.",
            )

    
        self.save_conversation_message(
            role="user",
            content=command,
        )

        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

        # Profile questions are answered directly from user_profile.json.
        # They remain available even when Gemini or the internet is down.
        stage("Checking local profile")
        local_profile_answer = self.user_profile.answer_query(command)

        if local_profile_answer is not None:
            report = ExecutionReport(
                goal="Answer from editable user profile",
                success=True,
                completed_steps=0,
                total_steps=0,
                message=local_profile_answer,
            )
            self.save_report_to_memory(
                command=command,
                report=report,
            )
            return report

        stage("Loading memory")
        memory_context = self.get_memory_context()
        conversation_context = (
            self.get_recent_conversation_context()
        )

        print("\n[Long-term memory context]")
        print(memory_context)

        print("\n[Recent conversation context]")
        print(conversation_context)

        stage("Understanding request")
        plan = self.planner.create_plan(
            command=command,
            memory_context=memory_context,
            conversation_context=conversation_context,
        )

        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

        if not plan.steps:
            has_answer = bool(plan.message.strip())
            is_ai_error = self.is_ai_error_message(plan.message)

            report = ExecutionReport(
                goal=plan.goal,
                success=(has_answer and not is_ai_error),
                completed_steps=0,
                total_steps=0,
                message=(
                    plan.message
                    or "MV.AI could not create a response."
                ),
            )

            self.save_report_to_memory(
                command=command,
                report=report,
            )

            return report

        stage(
            "Executing",
            0,
            len(plan.steps),
            None,
        )
        report = self.executor.execute_plan(
            plan=plan,
            confirmation_callback=confirmation_callback,
            progress_callback=progress_callback,
            cancellation_token=cancellation_token,
        )

        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

        stage("Saving result")
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

        self.save_report_to_memory(
            command=command,
            report=report,
        )

        return report

    def import_image_attachment(
        self,
        source_path: str,
    ) -> dict:
        """Copy a selected image into MV.ai's private media directory."""

        return self.media_store.store_image(source_path).to_dict()

    def handle_image_command(
        self,
        command: str,
        attachment: dict,
        cancellation_token: CancellationToken | None = None,
        stage_callback=None,
    ) -> ExecutionReport:
        """Answer a question about one attached image without using the tool planner."""

        command = command.strip() or "Describe this image and its important details."

        def stage(name: str, current: int = 0, total: int = 0, detail=None) -> None:
            if callable(stage_callback):
                stage_callback(name, current, total, detail)

        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

        image_path = self.media_store.resolve_path(attachment)
        if image_path is None:
            return ExecutionReport(
                goal="Analyze attached image",
                success=False,
                completed_steps=0,
                total_steps=0,
                message="The attached image is no longer available.",
            )

        # Load prior context before saving the current request so the image
        # question is not repeated twice in the Gemini prompt.
        profile_context = self.user_profile.get_context()
        conversation_context = self.get_recent_conversation_context(limit=4)

        self.save_conversation_message(
            role="user",
            content=command,
            attachments=[attachment],
        )

        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

        stage("Analyzing image")
        vision_prompt = (
            f"USER REQUEST:\n{command}\n\n"
            f"USER PROFILE CONTEXT:\n{profile_context}\n\n"
            f"RECENT CONVERSATION CONTEXT:\n{conversation_context}"
        )

        response = self.ai_provider.analyze_image(
            image_path=image_path,
            prompt=vision_prompt,
            mime_type=str(attachment.get("mime_type", "")),
        )

        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

        normalized_response = response.strip().lower()
        local_vision_errors = (
            "the attached image is no longer available",
            "mv.ai could not read the attached image",
            "the attached image is empty",
            "mv.ai vision currently supports",
        )
        success = (
            bool(response.strip())
            and not self.is_ai_error_message(response)
            and not any(marker in normalized_response for marker in local_vision_errors)
        )
        report = ExecutionReport(
            goal="Analyze attached image",
            success=success,
            completed_steps=1 if success else 0,
            total_steps=1,
            message=response,
        )
        stage("Saving result")
        self.save_report_to_memory(command=command, report=report)
        return report

    @staticmethod
    def is_ai_error_message(message: str) -> bool:
        """Return True when a no-step plan contains an AI service error."""

        normalized = str(message).strip().lower()
        if not normalized:
            return False

        markers = (
            "gemini is temporarily unavailable",
            "gemini is not configured",
            "gemini authentication failed",
            "gemini could not complete that request",
            "gemini request failed",
            "could not initialize gemini",
            "all available gemini models failed",
            "the ai planner failed",
        )
        return any(marker in normalized for marker in markers)

    def get_memory_context(
        self,
        limit: int = 8,
    ) -> str:
        """
        Return the editable profile and database memories as prompt context.

        user_profile.json is re-read for every command, so manual edits are
        available immediately without changing Python code or restarting MV.ai.
        """

        profile_context = self.user_profile.get_context()

        try:
            database_context = self.memory.get_memory_context(
                limit=limit
            )
        except Exception as error:
            print(
                "[Memory warning] Could not load "
                f"long-term memory: {error}"
            )
            database_context = (
                "Dynamic long-term memory is currently unavailable."
            )

        return (
            f"{profile_context}\n\n"
            "DYNAMIC LONG-TERM MEMORY:\n"
            f"{database_context}"
        )

    def get_recent_conversation_context(
        self,
        limit: int = 4,
    ) -> str:
        """
        Return recent messages from the current session.
        """

        try:
            messages = self.memory.get_conversation_history(
                limit=limit
            )
        except Exception as error:
            print(
                "[Memory warning] Could not load "
                f"conversation history: {error}"
            )
            return "No recent conversation is available."

        if not messages:
            return "No recent conversation is available."

        lines = ["Recent conversation:"]

        for message in messages:
            role = message.get("role", "unknown")
            content = message.get("content", "")
            lines.append(
                f"{role.capitalize()}: {content}"
            )

        return "\n".join(lines)

    def save_conversation_message(
        self,
        role: str,
        content: str,
        attachments: list[dict] | None = None,
    ) -> None:
        """
        Save one conversation message safely.
        """

        if not content or not content.strip():
            return

        try:
            self.memory.add_conversation_message(
                role=role,
                content=content,
                attachments=attachments,
            )

            if role.strip().lower() == "user":
                self.realities.ensure_current_title(
                    content
                )

        except Exception as error:
            print(
                "[Memory warning] Could not save "
                f"{role} message: {error}"
            )

    def save_report_to_memory(
        self,
        command: str,
        report: ExecutionReport,
    ) -> None:
        """
        Save MV.AI's response and command execution result.
        """

        response_text = self.get_report_response_text(report)

        self.save_conversation_message(
            role="assistant",
            content=response_text,
        )

        error_message = None

        if not report.success:
            failed_results = [
                result
                for result in report.results
                if not result.success
            ]

            if failed_results:
                error_message = failed_results[-1].error
            elif report.message:
                error_message = report.message

        try:
            self.memory.log_command(
                command=command,
                success=report.success,
                response=response_text,
                error=error_message,
            )
        except Exception as error:
            print(
                "[Memory warning] Could not log "
                f"command: {error}"
            )

    @staticmethod
    def get_report_response_text(
        report: ExecutionReport,
    ) -> str:
        """Return the same useful result text that the desktop UI shows."""

        if report.success:
            outputs = []
            for result in report.results:
                if result.output is None:
                    continue
                output = str(result.output).strip()
                if output:
                    outputs.append(output)

            if outputs:
                return "\n".join(outputs)

            return report.message or "Task completed successfully."

        error_parts = []
        if report.message:
            error_parts.append(report.message)

        for result in report.results:
            if result.error:
                error_parts.append(result.error)

        if error_parts:
            return "\n".join(dict.fromkeys(error_parts))

        return "The task could not be completed."

    def start_new_reality(self) -> str:
        """
        End the active conversation and create a new reality.
        """

        return self.realities.create_new_reality()

    def get_recent_realities(
        self,
        limit: int = 30,
    ) -> list[dict]:
        """
        Return recent saved realities for the desktop UI.
        """

        return self.realities.get_recent_realities(
            limit=limit
        )

    def load_reality(
        self,
        session_id: str,
    ) -> list[dict]:
        """
        Switch to a saved reality and return its messages.
        """

        return self.realities.load_reality(
            session_id=session_id
        )

    def get_current_reality_id(self) -> str:
        return (
            self.realities
            .get_current_reality_id()
        )

    def clear_all_realities(self) -> str:
        """
        Delete saved conversation realities while preserving
        long-term personal memories and command history.
        """

        return (
            self.realities
            .clear_all_realities()
        )

    def create_plan(self, command: str):
        """
        Create a memory-aware plan without executing it.
        """

        memory_context = self.get_memory_context()
        conversation_context = (
            self.get_recent_conversation_context()
        )

        return self.planner.create_plan(
            command=command,
            memory_context=memory_context,
            conversation_context=conversation_context,
        )

    def execute(self, tool_name, args=None):
        """
        Execute one registered tool directly.
        """

        return self.registry.execute(
            tool_name,
            args,
        )

    def list_tools(self) -> list[str]:
        return self.registry.list_tools()

    def get_plugin_errors(self) -> list[str]:
        return list(self.plugin_errors)

    def get_ai_status(self) -> str:
        return self.planner.get_status()

    def get_memory_status(self) -> dict:
        """
        Return basic information about the memory database.
        """

        try:
            memories = self.memory.get_all_memories(
                limit=500
            )
            commands = self.memory.get_recent_commands(
                limit=20
            )
            messages = self.memory.get_conversation_history(
                limit=20
            )

            return {
                "ready": True,
                "session_id": self.memory.session_id,
                "memory_count": len(memories),
                "recent_command_count": len(commands),
                "recent_message_count": len(messages),
                "user_profile": self.user_profile.get_status(),
            }
        except Exception as error:
            return {
                "ready": False,
                "error": str(error),
            }

    def get_status(self) -> dict:
        """
        Return status information for the desktop UI.
        """

        return {
            "ai": self.get_ai_status(),
            "memory": self.get_memory_status(),
            "tools": self.list_tools(),
            "plugin_errors": self.get_plugin_errors(),
        }

    def shutdown(self) -> None:
        """
        End the active memory session cleanly.
        """

        try:
            self.memory.end_session()
        except Exception as error:
            print(
                "[Memory warning] Could not end "
                f"memory session: {error}"
            )