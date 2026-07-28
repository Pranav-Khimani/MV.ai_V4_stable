from __future__ import annotations

import json
from collections.abc import Iterable

from core.tool_schema import PERMISSION_CONFIRM, ToolSchema


BASE_SYSTEM_PROMPT = """
You are the planning engine of MV.ai, a Windows desktop AI assistant.

MV.ai communicates through text and a desktop voice system. Never claim that
MV.ai is text-only or cannot speak.

Your job is to convert the user's request into a clear task plan. You do not
execute tools and you never claim an action succeeded before a tool reports it.

Return ONLY valid JSON. Do not use Markdown, code fences, or text outside JSON.

Use this exact structure:
{
  "goal": "Brief description of the user's goal",
  "steps": [
    {
      "device": "laptop",
      "tool": "tool name",
      "args": {
        "action": "action name"
      },
      "description": "Brief explanation of this step"
    }
  ],
  "message": ""
}

PLANNING RULES

1. The steps field must always be a list.
2. Each step must use exactly one registered tool action.
3. Use only devices, tools, actions, and argument names listed below.
4. Never invent tools, files, folders, apps, websites, recipients, messages,
   or user information.
5. Preserve important names exactly as the user supplied them.
6. Percentages must be numeric values from 0 to 100.
7. Put steps in execution order and keep descriptions short and factual.
8. The permission system handles confirmation; do not claim confirmation was
   granted and do not claim the action already happened.
9. If required information is missing and guessing is unsafe or unreliable,
   return no steps and explain what is missing in message.
10. Greetings and normal conversation are not executable tasks. Return no
    steps and place the answer in message.
11. For a normal question requiring no tool, return no steps and put the
    answer in message.
12. If a requested device capability is not listed, do not invent it. Explain
    the missing capability in message.
""".strip()


GENERAL_EXAMPLES = """
EXAMPLES

User: Open YouTube.
Response:
{"goal":"Open YouTube","steps":[{"device":"laptop","tool":"browser","args":{"action":"open_website","query":"youtube"},"description":"Open YouTube in the default browser."}],"message":""}

User: Open VS Code and set the volume to 40 percent.
Response:
{"goal":"Open VS Code and adjust volume","steps":[{"device":"laptop","tool":"apps","args":{"action":"open_app","app_name":"VS Code"},"description":"Open VS Code."},{"device":"laptop","tool":"device","args":{"action":"set_volume","level":40},"description":"Set volume to 40 percent."}],"message":""}

User: Hi.
Response:
{"goal":"","steps":[],"message":"Hi! What would you like me to help with?"}
""".strip()


def build_system_prompt(schemas: Iterable[ToolSchema]) -> str:
    """Build Gemini's tool instructions from registered tool schemas."""

    schema_list = sorted(schemas, key=lambda schema: schema.name)
    devices = sorted(
        {
            device
            for schema in schema_list
            for device in schema.devices
        }
    )

    sections = [
        BASE_SYSTEM_PROMPT,
        "SUPPORTED DEVICES\n\n" + "\n".join(f"- {d}" for d in devices),
        "AVAILABLE TOOLS",
    ]

    for schema in schema_list:
        sections.append(_render_tool(schema))

    if "phone" not in devices:
        sections.append(
            "PHONE CAPABILITY\n\n"
            "No phone tools are currently registered. Do not create phone "
            "steps or invent phone capabilities."
        )

    sections.append(GENERAL_EXAMPLES)
    return "\n\n".join(sections).strip()


def _render_tool(schema: ToolSchema) -> str:
    lines = [
        f"TOOL: {schema.name}",
        f"Description: {schema.description}",
        "Devices: " + ", ".join(schema.devices),
    ]

    if schema.prompt_rules:
        lines.append("Tool rules:")
        lines.extend(f"- {rule}" for rule in schema.prompt_rules)

    lines.append("Actions:")

    for action_name, action in sorted(schema.actions.items()):
        example = {
            "action": action_name,
            **dict(action.example),
        }
        lines.extend(
            [
                f"\nACTION: {action_name}",
                f"Description: {action.description}",
                "Required arguments: "
                + (", ".join(action.required_arguments) or "none"),
                "Optional arguments: "
                + (", ".join(action.optional_arguments) or "none"),
                "Permission: "
                + (
                    "confirmation required"
                    if action.permission == PERMISSION_CONFIRM
                    else "no confirmation required"
                ),
                "Arguments example: "
                + json.dumps(example, ensure_ascii=False),
            ]
        )

        if action.prompt_rules:
            lines.append("Action rules:")
            lines.extend(
                f"- {rule}"
                for rule in action.prompt_rules
            )

    return "\n".join(lines)
