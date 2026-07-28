# app_tool.py
import os
import shutil
import subprocess
from pathlib import Path
from core.tool import Tool

class AppTool(Tool):
    name = "apps"
    description = "Launch installed Windows applications."

    APPS = {
        "calculator":{"aliases":["calculator","calc"],"commands":["calc.exe"]},
        "notepad":{"aliases":["notepad"],"commands":["notepad.exe"]},
        "paint":{"aliases":["paint","mspaint"],"commands":["mspaint.exe"]},
        "cmd":{"aliases":["cmd","command prompt"],"commands":["cmd.exe"]},
        "terminal":{"aliases":["terminal","windows terminal"],"commands":["wt.exe"]},
        "explorer":{"aliases":["explorer","file explorer"],"commands":["explorer.exe"]},
        "vscode":{
            "aliases":["vs code","vscode","visual studio code","code"],
            "commands":["code"],
            "paths":[
                Path.home()/"AppData/Local/Programs/Microsoft VS Code/Code.exe",
                Path("C:/Program Files/Microsoft VS Code/Code.exe"),
                Path("C:/Program Files (x86)/Microsoft VS Code/Code.exe"),
            ],
        },
        "chrome":{
            "aliases":["chrome","google chrome"],
            "commands":["chrome"],
            "paths":[
                Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
                Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
                Path.home()/"AppData/Local/Google/Chrome/Application/chrome.exe",
            ],
        },
        "edge":{"aliases":["edge","microsoft edge"],"commands":["msedge"]},
        "firefox":{"aliases":["firefox"],"commands":["firefox"]},
        "brave":{"aliases":["brave","brave browser"],"commands":["brave"]},
        "spotify":{
            "aliases":["spotify","spotify app"],
            "uri":"spotify:",
            "commands":["spotify"],
            "paths":[
                Path.home()/"AppData/Roaming/Spotify/Spotify.exe",
                Path.home()/"AppData/Local/Microsoft/WindowsApps/Spotify.exe",
                Path("C:/Program Files/Spotify/Spotify.exe"),
                Path("C:/Program Files (x86)/Spotify/Spotify.exe"),
            ],
        },
        "discord":{"aliases":["discord"],"commands":["discord"]},
        "steam":{"aliases":["steam"],"uri":"steam:","commands":["steam"]},
        "settings":{"aliases":["settings","windows settings"],"uri":"ms-settings:"},
    }

    def execute(self,args=None):
        if not args:
            return "Please provide an app action."
        if args.get("action")!="open_app":
            return f"Unknown app action: {args.get('action')}"
        return self.open_app(args.get("app_name"))

    def open_app(self, app_name):
        if not app_name:
            return "Please provide an application name."
        q=app_name.lower().strip()
        app=self._find(q)
        if not app:
            return f"I don't know how to open '{app_name}' yet."
        if app.get("uri"):
            try:
                os.startfile(app["uri"])
                return f"Opened {app_name}."
            except Exception:
                pass
        for cmd in app.get("commands",[]):
            exe=shutil.which(cmd) or cmd
            try:
                subprocess.Popen([exe])
                return f"Opened {app_name}."
            except Exception:
                pass
        for p in app.get("paths",[]):
            if p.exists():
                os.startfile(str(p))
                return f"Opened {app_name}."
        return f"{app_name} does not appear to be installed."

    def _find(self,name):
        for app in self.APPS.values():
            if name in app["aliases"]:
                return app
        return None