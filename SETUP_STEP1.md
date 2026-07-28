# MV.ai v0.9 — Step 1: Secure and Clean

## What was changed

- Removed the real `.env` file.
- Removed `.env` from the PyInstaller bundle.
- Removed `build/`, `dist/`, local databases, caches, logs, backups, and compiled Python files.
- Added a stronger `.gitignore`.
- Added `.env.example`.
- Added `requirements.txt`.
- Added `RUN_MVAI.bat`, which starts the project from the correct root directory.

## First-time setup

1. Install Python 3.12.
2. Open a terminal in this folder.
3. Run:

   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. Copy `.env.example` and rename the copy to `.env`.
5. Put your newly rotated private credentials in `.env`.
6. Start MV.ai by double-clicking `RUN_MVAI.bat`, or run:

   ```bat
   python app.py
   ```

Do not run `ui/window.py` directly. That causes `ModuleNotFoundError: No module named 'core'` because it bypasses the project root entry point.

## Build command

After testing the source version:

```bat
python -m PyInstaller --clean --noconfirm MV.ai.spec
```

The `.env` file is intentionally not included in the build.
