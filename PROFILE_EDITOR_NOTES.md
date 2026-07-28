# MV.ai V4 — Editable Profile Tab

## Added

- Editable Personal, Education, Preferences, and Projects fields.
- Custom facts table with add/remove controls.
- Safe atomic saving to `user_profile.json`.
- Reload button and visible saved/unsaved/error states.
- Raw JSON button for advanced nested data.
- Preservation of unknown profile sections and keys.
- Numeric and JSON value support for custom facts.

## Safety

The patch does not include or replace `.env`, `.venv`, or `user_profile.json`.
Do not store credentials or highly private data in the profile.
