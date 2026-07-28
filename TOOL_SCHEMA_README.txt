MV.ai CENTRAL TOOL SCHEMA
=========================

Every tool now declares these details inside its own Tool class:
- tool name
- description
- supported devices
- actions
- required and optional arguments
- permission level
- confirmation message
- prompt rules and examples

The following systems read the same declarations:
- TaskPlanner validation
- Gemini system prompt
- PermissionManager
- ToolRegistry

This removes duplicated TOOL_ACTIONS, REQUIRED_ARGUMENTS, LAPTOP_TOOLS,
and SENSITIVE_ACTIONS lists.

TEST
----
Run TEST_TOOL_SCHEMA.bat.

ADDING A TOOL ACTION LATER
--------------------------
1. Add the ActionSchema declaration to the tool class.
2. Implement the action in that tool's execute method.
3. Run TEST_TOOL_SCHEMA.bat.

Do not manually edit the planner, prompt, or permission manager for the
new action. They now read the tool's schema automatically.
