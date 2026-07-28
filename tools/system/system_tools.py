from datetime import datetime
import ctypes
import os

from core.tool import Tool
from core.tool_schema import ActionSchema, PERMISSION_CONFIRM


class SystemTool(Tool):
    name = "system"
    description = "Read time/date and control lock, restart, or shutdown."
    actions = {
        "time": ActionSchema(
            description="Return the current local time.",
            example={},
        ),
        "date": ActionSchema(
            description="Return the current local date.",
            example={},
        ),
        "lock": ActionSchema(
            description="Lock the computer.",
            permission=PERMISSION_CONFIRM,
            confirmation_message="Lock the computer?",
            example={},
        ),
        "restart": ActionSchema(
            description="Restart the computer immediately.",
            permission=PERMISSION_CONFIRM,
            confirmation_message="Restart the computer immediately?",
            example={},
        ),
        "shutdown": ActionSchema(
            description="Shut down the computer immediately.",
            permission=PERMISSION_CONFIRM,
            confirmation_message="Shut down the computer immediately?",
            example={},
        ),
    }

    def execute(self, args=None):
        if not args:
            return "No system action provided."

        action = args.get("action")

        if action == "time":
            return self.get_time()

        if action == "date":
            return self.get_date()

        if action == "lock":
            return self.lock_pc()

        if action == "restart":
            return self.restart_pc()

        if action == "shutdown":
            return self.shutdown_pc()

        return "Unknown system action."

    def get_time(self):
        return datetime.now().strftime("%I:%M:%S %p")

    def get_date(self):
        return datetime.now().strftime("%A, %d %B %Y")

    def lock_pc(self):
        ctypes.windll.user32.LockWorkStation()
        return "Computer locked."

    def restart_pc(self):
        os.system("shutdown /r /t 0")
        return "Restarting computer..."

    def shutdown_pc(self):
        os.system("shutdown /s /t 0")
        return "Shutting down computer..."