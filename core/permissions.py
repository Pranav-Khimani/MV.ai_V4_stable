class PermissionManager:
    """Central confirmation policy for sensitive MV.ai actions."""

    SENSITIVE_ACTIONS = {
        ("system", "lock"): "Lock the computer?",
        ("system", "restart"): "Restart the computer immediately?",
        ("system", "shutdown"): "Shut down the computer immediately?",
        ("files", "rename_file"): "Rename this file?",
        ("files", "move_file"): "Move this file?",
        ("files", "delete_file"): "Delete this file permanently?",
        ("files", "delete_folder"): "Delete this empty folder permanently?",
        ("device", "wifi_disconnect"): "Disconnect this computer from Wi-Fi?",
        ("email", "send_email"): "Send this email now?",
    }

    def requires_confirmation(
        self,
        tool_name: str,
        action: str,
    ) -> bool:
        """Return True when a tool action needs user confirmation."""

        return (tool_name, action) in self.SENSITIVE_ACTIONS

    def get_confirmation_message(
        self,
        tool_name: str,
        action: str,
    ) -> str:
        """Return the confirmation message for an action."""

        return self.SENSITIVE_ACTIONS.get(
            (tool_name, action),
            f"Allow '{action}'?",
        )

    def apply_policy(self, parsed: dict) -> dict:
        """Keep compatibility with the older rule-based parser."""

        tool_name = parsed.get("tool")
        args = parsed.get("args") or {}
        action = args.get("action")

        policy_message = self.SENSITIVE_ACTIONS.get(
            (tool_name, action)
        )

        if policy_message:
            parsed["requires_confirmation"] = True
            parsed["confirmation_message"] = policy_message

        return parsed

    def confirm(self, message: str) -> bool:
        """Temporary terminal confirmation for non-GUI use."""

        print()
        print("MV.AI:", message)

        answer = input("(yes/no): ").strip().lower()
        return answer in {"yes", "y"}
