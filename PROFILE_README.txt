MV.ai EDITABLE USER PROFILE
===========================

1. Double-click EDIT_MY_PROFILE.bat.
2. Edit user_profile.json.
3. Save it.
4. Your changes are loaded for MV.ai's next command. A restart is not needed.

Examples of fields you may add:

  "personal": {
    "name": "Pranav",
    "nickname": "Multiverse",
    "age": 16
  }

  "preferences": {
    "preferred_editor": "VS Code",
    "favorite_game": "Minecraft"
  }

  "custom": {
    "anything_you_want": "Any useful fact"
  }

JSON RULES
----------
- Text must be inside double quotes.
- Put a comma after every item except the last item in a section.
- Numbers do not need quotes.
- Use true or false for yes/no values.
- Do not delete the opening or closing braces.

PRIVACY
-------
Do not put passwords, API keys, bank information, exact home addresses,
or other secrets in this file. Profile facts are supplied to the AI model
as context when MV.ai processes your commands.
