"""MV.ai email-intent regression tests."""

from ai.planner import TaskPlanner


class FailProvider:
    """The direct parser must not call Gemini for complete commands."""

    def generate_plan(self, command):
        raise AssertionError(
            "Gemini was called for a complete email command."
        )


def check(command, expected_to, expected_subject, expected_body, expected_mode):
    plan = TaskPlanner(FailProvider()).create_plan(command)

    assert plan.steps, plan.message
    args = plan.steps[0].args

    assert args["to"] == expected_to
    assert args["subject"] == expected_subject
    assert args["body"] == expected_body
    assert args["body_mode"] == expected_mode


check(
    (
        "send an email to sagarent.mumbai@gmail.com about stock "
        "trading and this is a test from mv.ai, with the subject "
        "mv.ai test."
    ),
    "sagarent.mumbai@gmail.com",
    "mv.ai test",
    (
        "Hi,\n\nI'm writing about stock trading. "
        "This is a test from mv.ai.\n\nBest regards,"
    ),
    "composed",
)

check(
    (
        "Send an email to alex@example.com saying I will arrive "
        "at 5, with subject Arrival time."
    ),
    "alex@example.com",
    "Arrival time",
    "I will arrive at 5",
    "exact",
)

assert TaskPlanner.try_create_direct_email_plan(
    "send an email to alex@example.com about stock trading"
) is None

print("[PASSED] Email topic and exact-message parsing work correctly.")
