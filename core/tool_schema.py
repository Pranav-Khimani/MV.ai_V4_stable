from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


PERMISSION_NONE = "none"
PERMISSION_CONFIRM = "confirm"
VALID_PERMISSION_LEVELS = {
    PERMISSION_NONE,
    PERMISSION_CONFIRM,
}


@dataclass(frozen=True)
class ActionSchema:
    """Declarative contract for one tool action."""

    description: str
    required_arguments: tuple[str, ...] = ()
    optional_arguments: tuple[str, ...] = ()
    permission: str = PERMISSION_NONE
    confirmation_message: str = ""
    example: Mapping[str, Any] = field(default_factory=dict)
    prompt_rules: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        description = self.description.strip()
        if not description:
            raise ValueError("Action description cannot be empty.")

        required = self._normalize_argument_names(
            self.required_arguments,
            "required",
        )
        optional = self._normalize_argument_names(
            self.optional_arguments,
            "optional",
        )

        overlap = set(required).intersection(optional)
        if overlap:
            joined = ", ".join(sorted(overlap))
            raise ValueError(
                f"Arguments cannot be both required and optional: {joined}."
            )

        permission = self.permission.strip().lower()
        if permission not in VALID_PERMISSION_LEVELS:
            raise ValueError(
                f"Unsupported permission level '{self.permission}'."
            )

        confirmation_message = self.confirmation_message.strip()
        if permission == PERMISSION_CONFIRM and not confirmation_message:
            raise ValueError(
                "A confirmation message is required for confirm actions."
            )

        example = dict(self.example)
        example_keys = set(example)
        missing_example_values = set(required).difference(example_keys)
        if missing_example_values:
            joined = ", ".join(sorted(missing_example_values))
            raise ValueError(
                "Action examples must include every required argument: "
                f"{joined}."
            )

        object.__setattr__(self, "description", description)
        object.__setattr__(self, "required_arguments", required)
        object.__setattr__(self, "optional_arguments", optional)
        object.__setattr__(self, "permission", permission)
        object.__setattr__(self, "confirmation_message", confirmation_message)
        object.__setattr__(self, "example", example)
        object.__setattr__(
            self,
            "prompt_rules",
            tuple(
                rule.strip()
                for rule in self.prompt_rules
                if str(rule).strip()
            ),
        )

    @staticmethod
    def _normalize_argument_names(
        names: tuple[str, ...],
        kind: str,
    ) -> tuple[str, ...]:
        normalized: list[str] = []

        for raw_name in names:
            name = str(raw_name).strip()
            if not name:
                raise ValueError(
                    f"An {kind} argument name cannot be empty."
                )
            if name == "action":
                raise ValueError(
                    "Do not declare 'action' as a required or optional argument."
                )
            if name in normalized:
                raise ValueError(
                    f"Duplicate {kind} argument '{name}'."
                )
            normalized.append(name)

        return tuple(normalized)


@dataclass(frozen=True)
class ToolSchema:
    """Complete declarative contract for one MV.ai tool."""

    name: str
    description: str
    devices: tuple[str, ...]
    actions: Mapping[str, ActionSchema]
    prompt_rules: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        name = self.name.strip().lower()
        description = self.description.strip()
        devices = tuple(
            device.strip().lower()
            for device in self.devices
            if str(device).strip()
        )
        actions = {
            action_name.strip().lower(): action_schema
            for action_name, action_schema in self.actions.items()
        }

        if not name:
            raise ValueError("Tool name cannot be empty.")
        if not description:
            raise ValueError(f"Tool '{name}' needs a description.")
        if not devices:
            raise ValueError(f"Tool '{name}' must support at least one device.")
        if len(set(devices)) != len(devices):
            raise ValueError(f"Tool '{name}' contains duplicate devices.")
        if not actions:
            raise ValueError(f"Tool '{name}' must declare at least one action.")

        for action_name, action_schema in actions.items():
            if not action_name:
                raise ValueError(f"Tool '{name}' has an empty action name.")
            if not isinstance(action_schema, ActionSchema):
                raise TypeError(
                    f"Tool '{name}' action '{action_name}' must use ActionSchema."
                )

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "devices", devices)
        object.__setattr__(self, "actions", actions)
        object.__setattr__(
            self,
            "prompt_rules",
            tuple(
                rule.strip()
                for rule in self.prompt_rules
                if str(rule).strip()
            ),
        )
