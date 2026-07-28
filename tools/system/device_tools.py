import os
import re
import subprocess
import tkinter as tk

from core.tool import Tool
from core.tool_schema import ActionSchema, PERMISSION_CONFIRM


class DeviceTool(Tool):
    name = "device"
    description = (
        "Read battery status and control clipboard, volume, brightness, "
        "Wi-Fi, and camera."
    )
    actions = {
        "battery": ActionSchema(
            description="Read battery percentage and charging status.",
            example={},
        ),
        "read_clipboard": ActionSchema(
            description="Read text currently stored in the clipboard.",
            example={},
        ),
        "write_clipboard": ActionSchema(
            description="Copy text to the clipboard.",
            required_arguments=("text",),
            example={"text": "Text to copy"},
        ),
        "get_volume": ActionSchema(
            description="Read the current volume level.",
            example={},
        ),
        "set_volume": ActionSchema(
            description="Set volume to a percentage from 0 to 100.",
            required_arguments=("level",),
            example={"level": 40},
        ),
        "volume_up": ActionSchema(
            description="Increase volume by a small amount.",
            example={},
        ),
        "volume_down": ActionSchema(
            description="Decrease volume by a small amount.",
            example={},
        ),
        "mute": ActionSchema(
            description="Mute the computer.",
            example={},
        ),
        "unmute": ActionSchema(
            description="Unmute the computer.",
            example={},
        ),
        "get_brightness": ActionSchema(
            description="Read the current display brightness.",
            example={},
        ),
        "set_brightness": ActionSchema(
            description="Set display brightness from 0 to 100.",
            required_arguments=("level",),
            example={"level": 60},
        ),
        "brightness_up": ActionSchema(
            description="Increase brightness by a small amount.",
            example={},
        ),
        "brightness_down": ActionSchema(
            description="Decrease brightness by a small amount.",
            example={},
        ),
        "wifi_status": ActionSchema(
            description="Read the connected Wi-Fi network and signal.",
            example={},
        ),
        "wifi_networks": ActionSchema(
            description="List visible Wi-Fi networks.",
            example={},
        ),
        "wifi_disconnect": ActionSchema(
            description="Disconnect the computer from Wi-Fi.",
            permission=PERMISSION_CONFIRM,
            confirmation_message="Disconnect this computer from Wi-Fi?",
            example={},
        ),
        "open_camera": ActionSchema(
            description="Open the Windows Camera application.",
            example={},
        ),
    }

    def execute(self, args=None):
        if not args:
            return "Please provide a device action."

        action = args.get("action")

        actions = {
            "battery": self.get_battery,
            "read_clipboard": self.read_clipboard,
            "write_clipboard": lambda: self.write_clipboard(
                args.get("text")
            ),
            "get_volume": self.get_volume,
            "set_volume": lambda: self.set_volume(
                args.get("level")
            ),
            "volume_up": self.volume_up,
            "volume_down": self.volume_down,
            "mute": lambda: self.set_mute(True),
            "unmute": lambda: self.set_mute(False),
            "get_brightness": self.get_brightness,
            "set_brightness": lambda: self.set_brightness(
                args.get("level")
            ),
            "brightness_up": self.brightness_up,
            "brightness_down": self.brightness_down,
            "wifi_status": self.wifi_status,
            "wifi_networks": self.list_wifi_networks,
            "wifi_disconnect": self.disconnect_wifi,
            "open_camera": self.open_camera,
        }

        function = actions.get(action)

        if function is None:
            return f"Unknown device action: {action}"

        try:
            return function()

        except Exception as error:
            return f"Device action failed: {error}"

    # -------------------------------------------------
    # Battery
    # -------------------------------------------------

    def get_battery(self):
        try:
            import psutil
        except ImportError:
            return (
                "Battery support is not installed. Run: "
                "python -m pip install psutil"
            )

        battery = psutil.sensors_battery()

        if battery is None:
            return "No battery was detected. This may be a desktop computer."

        percentage = round(battery.percent)
        charging = battery.power_plugged

        if charging:
            status = "charging"
        else:
            status = "not charging"

        return f"Battery is at {percentage}% and is {status}."

    # -------------------------------------------------
    # Clipboard
    # -------------------------------------------------

    def create_clipboard_window(self):
        window = tk.Tk()
        window.withdraw()
        window.update()

        return window

    def read_clipboard(self):
        window = self.create_clipboard_window()

        try:
            text = window.clipboard_get()

            if not text.strip():
                return "The clipboard is empty."

            return f"Clipboard:\n{text}"

        except tk.TclError:
            return "The clipboard does not currently contain readable text."

        finally:
            window.destroy()

    def write_clipboard(self, text):
        if not text:
            return "Please provide text to copy."

        window = self.create_clipboard_window()

        try:
            window.clipboard_clear()
            window.clipboard_append(text)
            window.update()

            return "Copied the text to your clipboard."

        finally:
            window.destroy()

    # -------------------------------------------------
    # Volume
    # -------------------------------------------------

    def get_volume_controller(self):
        try:
            from pycaw.pycaw import AudioUtilities
        except ImportError:
            return None

        device = AudioUtilities.GetSpeakers()
        return device.EndpointVolume

    def get_volume(self):
        volume = self.get_volume_controller()

        if volume is None:
            return (
                "Volume support is not installed. Run: "
                "python -m pip install pycaw"
            )

        level = round(
            volume.GetMasterVolumeLevelScalar() * 100
        )

        muted = bool(volume.GetMute())

        if muted:
            return f"Volume is {level}% and muted."

        return f"Volume is {level}%."

    def set_volume(self, level):
        volume = self.get_volume_controller()

        if volume is None:
            return (
                "Volume support is not installed. Run: "
                "python -m pip install pycaw"
            )

        level = self.validate_percentage(level)

        if level is None:
            return "Volume must be a number from 0 to 100."

        volume.SetMasterVolumeLevelScalar(
            level / 100,
            None,
        )

        if level > 0:
            volume.SetMute(0, None)

        return f"Volume set to {level}%."

    def change_volume(self, amount):
        volume = self.get_volume_controller()

        if volume is None:
            return (
                "Volume support is not installed. Run: "
                "python -m pip install pycaw"
            )

        current = round(
            volume.GetMasterVolumeLevelScalar() * 100
        )

        new_level = max(
            0,
            min(100, current + amount),
        )

        volume.SetMasterVolumeLevelScalar(
            new_level / 100,
            None,
        )

        if new_level > 0:
            volume.SetMute(0, None)

        return f"Volume set to {new_level}%."

    def volume_up(self):
        return self.change_volume(10)

    def volume_down(self):
        return self.change_volume(-10)

    def set_mute(self, muted):
        volume = self.get_volume_controller()

        if volume is None:
            return (
                "Volume support is not installed. Run: "
                "python -m pip install pycaw"
            )

        volume.SetMute(
            1 if muted else 0,
            None,
        )

        if muted:
            return "Volume muted."

        return "Volume unmuted."

    # -------------------------------------------------
    # Brightness
    # -------------------------------------------------

    def get_brightness_module(self):
        try:
            import screen_brightness_control as sbc
            return sbc

        except ImportError:
            return None

    def get_brightness(self):
        sbc = self.get_brightness_module()

        if sbc is None:
            return (
                "Brightness support is not installed. Run: "
                "python -m pip install screen-brightness-control"
            )

        levels = sbc.get_brightness()

        if not levels:
            return "No brightness-controlled display was detected."

        level = round(sum(levels) / len(levels))

        return f"Brightness is approximately {level}%."

    def set_brightness(self, level):
        sbc = self.get_brightness_module()

        if sbc is None:
            return (
                "Brightness support is not installed. Run: "
                "python -m pip install screen-brightness-control"
            )

        level = self.validate_percentage(level)

        if level is None:
            return "Brightness must be a number from 0 to 100."

        sbc.set_brightness(level)

        return f"Brightness set to {level}%."

    def change_brightness(self, amount):
        sbc = self.get_brightness_module()

        if sbc is None:
            return (
                "Brightness support is not installed. Run: "
                "python -m pip install screen-brightness-control"
            )

        levels = sbc.get_brightness()

        if not levels:
            return "No brightness-controlled display was detected."

        current = round(sum(levels) / len(levels))

        new_level = max(
            0,
            min(100, current + amount),
        )

        sbc.set_brightness(new_level)

        return f"Brightness set to {new_level}%."

    def brightness_up(self):
        return self.change_brightness(10)

    def brightness_down(self):
        return self.change_brightness(-10)

    # -------------------------------------------------
    # Wi-Fi
    # -------------------------------------------------

    def run_netsh(self, arguments):
        result = subprocess.run(
            ["netsh", "wlan", *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        output = result.stdout.strip()

        if not output:
            output = result.stderr.strip()

        return result.returncode, output

    def wifi_status(self):
        return_code, output = self.run_netsh(
            ["show", "interfaces"]
        )

        if return_code != 0:
            return f"Could not check Wi-Fi status:\n{output}"

        state_match = re.search(
            r"^\s*State\s*:\s*(.+)$",
            output,
            flags=re.IGNORECASE | re.MULTILINE,
        )

        ssid_match = re.search(
            r"^\s*SSID\s*:\s*(.+)$",
            output,
            flags=re.IGNORECASE | re.MULTILINE,
        )

        signal_match = re.search(
            r"^\s*Signal\s*:\s*(.+)$",
            output,
            flags=re.IGNORECASE | re.MULTILINE,
        )

        state = (
            state_match.group(1).strip()
            if state_match
            else "unknown"
        )

        if state.lower() != "connected":
            return f"Wi-Fi state: {state}."

        ssid = (
            ssid_match.group(1).strip()
            if ssid_match
            else "unknown network"
        )

        signal = (
            signal_match.group(1).strip()
            if signal_match
            else "unknown"
        )

        return (
            f"Connected to Wi-Fi network '{ssid}'. "
            f"Signal strength: {signal}."
        )

    def list_wifi_networks(self):
        return_code, output = self.run_netsh(
            ["show", "networks"]
        )

        if return_code != 0:
            return f"Could not list Wi-Fi networks:\n{output}"

        networks = re.findall(
            r"^\s*SSID\s+\d+\s*:\s*(.+)$",
            output,
            flags=re.IGNORECASE | re.MULTILINE,
        )

        networks = [
            network.strip()
            for network in networks
            if network.strip()
        ]

        if not networks:
            return "No visible Wi-Fi networks were found."

        lines = ["Visible Wi-Fi networks:"]

        for index, network in enumerate(networks, start=1):
            lines.append(f"{index}. {network}")

        return "\n".join(lines)

    def disconnect_wifi(self):
        return_code, output = self.run_netsh(
            ["disconnect"]
        )

        if return_code != 0:
            return f"Could not disconnect Wi-Fi:\n{output}"

        return "Wi-Fi disconnected."

    # -------------------------------------------------
    # Camera
    # -------------------------------------------------

    def open_camera(self):
        try:
            os.startfile("microsoft.windows.camera:")
            return "Opened the Camera app."

        except OSError as error:
            return f"Could not open the Camera app: {error}"

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------

    def validate_percentage(self, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return None

        if not 0 <= value <= 100:
            return None

        return value