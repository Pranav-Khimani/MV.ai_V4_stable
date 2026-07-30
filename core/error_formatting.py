"""Helpers for turning execution failures into clean user-facing messages."""

from __future__ import annotations

from collections.abc import Iterable


def merge_error_messages(
    report_message: str | None,
    result_errors: Iterable[str | None],
) -> str:
    """
    Merge report-level and step-level errors without repeating nested text.

    Example:
        report: "Task stopped at step 1: Device action failed: X"
        step:   "Device action failed: X"

    Only the complete report-level message should be shown.
    """

    merged: list[str] = []

    def add(candidate: str | None) -> None:
        if not candidate:
            return

        candidate = str(candidate).strip()
        if not candidate:
            return

        candidate_folded = candidate.casefold()

        for existing in tuple(merged):
            existing_folded = existing.casefold()

            if candidate_folded == existing_folded:
                return

            # Skip a shorter message already contained inside a more useful
            # report-level message.
            if candidate_folded in existing_folded:
                return

            # Replace a shorter existing message when the new one contains it.
            if existing_folded in candidate_folded:
                merged.remove(existing)

        merged.append(candidate)

    add(report_message)

    for error in result_errors:
        add(error)

    return "\n".join(merged)
