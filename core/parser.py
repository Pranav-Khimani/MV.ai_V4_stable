import re


class Parser:

    def parse(self, command):
        command = command.strip()
        lowered = command.lower()



        # Application commands

        app_aliases = {
            "calculator",
            "calc",
            "notepad",
            "paint",
            "command prompt",
            "cmd",
            "terminal",
            "file explorer",
            "explorer",
            "vs code",
            "vscode",
            "visual studio code",
            "chrome",
            "google chrome",
            "spotify",
        }

        if lowered.startswith("open app "):
            return self.create_result(
                "apps",
                "open_app",
                app_name=command[9:].strip(),
            )

        if lowered.startswith("launch "):
            return self.create_result(
                "apps",
                "open_app",
                app_name=command[7:].strip(),
            )

        if lowered.startswith("start "):
            return self.create_result(
                "apps",
                "open_app",
                app_name=command[6:].strip(),
            )

        if lowered.startswith("open "):
            possible_app = command[5:].strip().lower()

            if possible_app in app_aliases:
                return self.create_result(
                    "apps",
                    "open_app",
                    app_name=possible_app,
                )

        # Browser commands

        if lowered.startswith("google "):
            return self.create_result(
                "browser",
                "google_search",
                query=command[7:].strip(),
            )

        if lowered.startswith("search google for "):
            return self.create_result(
                "browser",
                "google_search",
                query=command[18:].strip(),
            )

        if lowered.startswith("youtube "):
            return self.create_result(
                "browser",
                "youtube_search",
                query=command[8:].strip(),
            )

        if lowered.startswith("search youtube for "):
            return self.create_result(
                "browser",
                "youtube_search",
                query=command[19:].strip(),
            )
        

                # ---------------------------------------------
        # Battery
        # ---------------------------------------------

        if lowered in {
            "battery",
            "battery status",
            "battery percentage",
            "how much battery do i have",
        }:
            return self.create_result(
                "device",
                "battery",
            )

        # ---------------------------------------------
        # Clipboard
        # ---------------------------------------------

        if lowered in {
            "read clipboard",
            "show clipboard",
            "what is in my clipboard",
        }:
            return self.create_result(
                "device",
                "read_clipboard",
            )

        clipboard_prefixes = (
            "copy to clipboard ",
            "set clipboard to ",
        )

        for prefix in clipboard_prefixes:
            if lowered.startswith(prefix):
                return self.create_result(
                    "device",
                    "write_clipboard",
                    text=command[len(prefix):].strip(),
                )

        # ---------------------------------------------
        # Volume
        # ---------------------------------------------

        if lowered in {
            "volume",
            "volume status",
            "what is the volume",
        }:
            return self.create_result(
                "device",
                "get_volume",
            )

        if lowered in {
            "volume up",
            "increase volume",
            "turn volume up",
        }:
            return self.create_result(
                "device",
                "volume_up",
            )

        if lowered in {
            "volume down",
            "decrease volume",
            "turn volume down",
        }:
            return self.create_result(
                "device",
                "volume_down",
            )

        if lowered in {
            "mute",
            "mute volume",
            "mute computer",
        }:
            return self.create_result(
                "device",
                "mute",
            )

        if lowered in {
            "unmute",
            "unmute volume",
            "unmute computer",
        }:
            return self.create_result(
                "device",
                "unmute",
            )

        volume_match = re.fullmatch(
            r"set volume(?: to)?\s+(\d{1,3})%?",
            lowered,
        )

        if volume_match:
            return self.create_result(
                "device",
                "set_volume",
                level=int(volume_match.group(1)),
            )

        # ---------------------------------------------
        # Brightness
        # ---------------------------------------------

        if lowered in {
            "brightness",
            "brightness status",
            "what is the brightness",
        }:
            return self.create_result(
                "device",
                "get_brightness",
            )

        if lowered in {
            "brightness up",
            "increase brightness",
            "turn brightness up",
        }:
            return self.create_result(
                "device",
                "brightness_up",
            )

        if lowered in {
            "brightness down",
            "decrease brightness",
            "turn brightness down",
        }:
            return self.create_result(
                "device",
                "brightness_down",
            )

        brightness_match = re.fullmatch(
            r"set brightness(?: to)?\s+(\d{1,3})%?",
            lowered,
        )

        if brightness_match:
            return self.create_result(
                "device",
                "set_brightness",
                level=int(brightness_match.group(1)),
            )

        # ---------------------------------------------
        # Wi-Fi
        # ---------------------------------------------

        if lowered in {
            "wifi",
            "wi-fi",
            "wifi status",
            "wi-fi status",
        }:
            return self.create_result(
                "device",
                "wifi_status",
            )

        if lowered in {
            "show wifi networks",
            "list wifi networks",
            "find wifi networks",
            "available wifi networks",
        }:
            return self.create_result(
                "device",
                "wifi_networks",
            )

        if lowered in {
            "disconnect wifi",
            "disconnect wi-fi",
        }:
            return {
                "tool": "device",
                "args": {
                    "action": "wifi_disconnect",
                },
                "requires_confirmation": True,
                "confirmation_message": (
                    "Disconnect this computer from Wi-Fi?"
                ),
            }

        # ---------------------------------------------
        # Camera
        # ---------------------------------------------

        if lowered in {
            "open camera",
            "launch camera",
            "start camera",
        }:
            return self.create_result(
                "device",
                "open_camera",
            )

        # Folder commands

        if lowered.startswith("open folder "):
            return self.create_result(
                "files",
                "open_folder",
                folder=command[12:].strip(),
            )

        folder_names = {
            "open desktop": "desktop",
            "open downloads": "downloads",
            "open documents": "documents",
            "open pictures": "pictures",
            "open music": "music",
            "open videos": "videos",
        }

        if lowered in folder_names:
            return self.create_result(
                "files",
                "open_folder",
                folder=folder_names[lowered],
            )

        create_match = re.fullmatch(
            r"create folder (.+?)(?: in (.+))?",
            command,
            flags=re.IGNORECASE,
        )

        if create_match:
            folder_name = create_match.group(1).strip()
            location = create_match.group(2)

            if location:
                location = location.strip()
            else:
                location = "desktop"

            return self.create_result(
                "files",
                "create_folder",
                folder_name=folder_name,
                location=location,
            )

        # File commands

        for prefix in (
            "find file ",
            "search file ",
            "search files for ",
            "find my ",
        ):
            if lowered.startswith(prefix):
                return self.create_result(
                    "files",
                    "search_files",
                    query=command[len(prefix):].strip(),
                )

        if lowered.startswith("open file "):
            return self.create_result(
                "files",
                "open_file",
                query=command[10:].strip(),
            )

        rename_match = re.fullmatch(
            r"rename file (.+?) to (.+)",
            command,
            flags=re.IGNORECASE,
        )

        if rename_match:
            return {
                "tool": "files",
                "args": {
                    "action": "rename_file",
                    "query": rename_match.group(1).strip(),
                    "new_name": rename_match.group(2).strip(),
                },
                "requires_confirmation": True,
                "confirmation_message": (
                    f"Rename '{rename_match.group(1).strip()}' "
                    f"to '{rename_match.group(2).strip()}'?"
                ),
            }

        copy_match = re.fullmatch(
            r"copy file (.+?) to (.+)",
            command,
            flags=re.IGNORECASE,
        )

        if copy_match:
            return self.create_result(
                "files",
                "copy_file",
                query=copy_match.group(1).strip(),
                destination=copy_match.group(2).strip(),
            )

        move_match = re.fullmatch(
            r"move file (.+?) to (.+)",
            command,
            flags=re.IGNORECASE,
        )

        if move_match:
            return {
                "tool": "files",
                "args": {
                    "action": "move_file",
                    "query": move_match.group(1).strip(),
                    "destination": move_match.group(2).strip(),
                },
                "requires_confirmation": True,
                "confirmation_message": (
                    f"Move '{move_match.group(1).strip()}' "
                    f"to {move_match.group(2).strip()}?"
                ),
            }
        
            
            # Time

        if lowered in [
            "time",
            "what time is it",
            "current time",
        ]:
            return self.create_result(
                "system",
                "time",
            )

        # Date

        if lowered in [
            "date",
            "today",
            "what is today's date",
            "current date",
        ]:
            return self.create_result(
                "system",
                "date",
            )

        # Lock

        if lowered == "lock computer":
            return {
                "tool": "system",
                "args": {
                    "action": "lock",
                },
                "requires_confirmation": True,
                "confirmation_message": "Lock the computer?",
            }

        # Restart

        if lowered == "restart computer":
            return {
                "tool": "system",
                "args": {
                    "action": "restart",
                },
                "requires_confirmation": True,
                "confirmation_message": "Restart the computer?",
            }

        # Shutdown

        if lowered == "shutdown computer":
            return {
                "tool": "system",
                "args": {
                    "action": "shutdown",
                },
                "requires_confirmation": True,
                "confirmation_message": "Shutdown the computer?",
            }

        # General website command comes after file/folder commands.
        if lowered.startswith("open "):
            return self.create_result(
                "browser",
                "open_website",
                query=command[5:].strip(),
            )

        return {
            "tool": None,
            "args": None,
            "requires_confirmation": False,
        }
    

    def create_result(self, tool, action, **arguments):
        return {
            "tool": tool,
            "args": {
                "action": action,
                **arguments,
            },
            "requires_confirmation": False,
        }
    
    