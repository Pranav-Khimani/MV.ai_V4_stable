import os
import re
import subprocess
import tkinter as tk
from contextlib import contextmanager

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

    @contextmanager
    def volume_session(self):
        """
        Open the Windows Core Audio endpoint inside the current thread.

        MV.ai executes tools on worker threads. COM must be initialized in
        the same thread that creates and uses the pycaw endpoint object.
        """

        try:
            from pycaw.pycaw import AudioUtilities
        except ImportError:
            yield None
            return

        com_initialized = False

        try:
            try:
                from comtypes import CoInitialize

                CoInitialize()
                com_initialized = True
            except Exception as error:
                # pycaw/comtypes may already have initialized COM. Continue
                # and let the actual endpoint call report a useful error.
                print(f"[VOLUME COM WARNING] {error}")

            device = AudioUtilities.GetSpeakers()
            yield device.EndpointVolume

        finally:
            if com_initialized:
                try:
                    from comtypes import CoUninitialize

                    CoUninitialize()
                except Exception as error:
                    print(f"[VOLUME COM CLEANUP WARNING] {error}")

    @staticmethod
    def _get_endpoint_volume_percent(volume) -> int:
        """Read volume as 0-100, with a dB fallback for odd drivers."""

        try:
            scalar = float(volume.GetMasterVolumeLevelScalar())
            return round(max(0.0, min(1.0, scalar)) * 100)
        except Exception as scalar_error:
            minimum_db, maximum_db, _ = volume.GetVolumeRange()
            current_db = float(volume.GetMasterVolumeLevel())

            minimum_db = float(minimum_db)
            maximum_db = float(maximum_db)

            if maximum_db <= minimum_db:
                raise RuntimeError(
                    "Windows returned an invalid volume range."
                ) from scalar_error

            ratio = (current_db - minimum_db) / (maximum_db - minimum_db)
            return round(max(0.0, min(1.0, ratio)) * 100)

    @staticmethod
    def _set_endpoint_volume_percent(volume, level: int) -> str:
        """
        Set volume using the normal scalar API, then fall back to decibels.

        A few Windows audio drivers reject SetMasterVolumeLevelScalar at
        boundary values such as 100 even though the endpoint itself works.
        SetMasterVolumeLevel with the endpoint's own dB range is a robust
        fallback for those devices.
        """

        scalar = max(0.0, min(1.0, float(level) / 100.0))
        scalar_error = None

        try:
            volume.SetMasterVolumeLevelScalar(float(scalar), None)
            return "scalar"
        except Exception as error:
            scalar_error = error
            print(f"[VOLUME SCALAR FALLBACK] {error}")

        try:
            minimum_db, maximum_db, _ = volume.GetVolumeRange()
            minimum_db = float(minimum_db)
            maximum_db = float(maximum_db)

            if level <= 0:
                target_db = minimum_db
            elif level >= 100:
                target_db = maximum_db
            else:
                target_db = minimum_db + (maximum_db - minimum_db) * scalar

            volume.SetMasterVolumeLevel(float(target_db), None)
            return "decibel"

        except Exception as decibel_error:
            raise RuntimeError(
                "Windows rejected both supported volume-control methods. "
                f"Scalar error: {scalar_error}; dB error: {decibel_error}"
            ) from decibel_error

    def get_volume(self):
        with self.volume_session() as volume:
            if volume is None:
                return (
                    "Volume support is not installed. Run: "
                    "python -m pip install pycaw"
                )

            try:
                level = self._get_endpoint_volume_percent(volume)
                muted = bool(volume.GetMute())
            except Exception as error:
                print(f"[VOLUME READ ERROR] {error}")
                return (
                    "Could not read the system volume. "
                    "Try reconnecting your audio device and restarting MV.ai."
                )

            if muted:
                return f"Volume is {level}% and muted."

            return f"Volume is {level}%."

    def set_volume(self, level):
        level = self.validate_percentage(level)

        if level is None:
            return "Volume must be a number from 0 to 100."

        with self.volume_session() as volume:
            if volume is None:
                return (
                    "Volume support is not installed. Run: "
                    "python -m pip install pycaw"
                )

            try:
                method = self._set_endpoint_volume_percent(volume, level)

                # Keep mute state intuitive: 0 is silent; any positive level
                # is unmuted. A mute failure should not undo a successful set.
                try:
                    volume.SetMute(1 if level == 0 else 0, None)
                except Exception as mute_error:
                    print(f"[VOLUME MUTE WARNING] {mute_error}")

                print(f"[VOLUME] Set to {level}% using {method} mode.")
                return f"Volume set to {level}%."

            except Exception as error:
                print(f"[VOLUME SET ERROR] {error}")
                return (
                    "Could not set the system volume. "
                    "Windows rejected the audio control request."
                )

    def change_volume(self, amount):
        with self.volume_session() as volume:
            if volume is None:
                return (
                    "Volume support is not installed. Run: "
                    "python -m pip install pycaw"
                )

            try:
                current = self._get_endpoint_volume_percent(volume)
                new_level = max(0, min(100, current + int(amount)))
                method = self._set_endpoint_volume_percent(volume, new_level)

                try:
                    volume.SetMute(1 if new_level == 0 else 0, None)
                except Exception as mute_error:
                    print(f"[VOLUME MUTE WARNING] {mute_error}")

                print(
                    f"[VOLUME] Changed from {current}% to {new_level}% "
                    f"using {method} mode."
                )
                return f"Volume set to {new_level}%."

            except Exception as error:
                print(f"[VOLUME CHANGE ERROR] {error}")
                return (
                    "Could not change the system volume. "
                    "Windows rejected the audio control request."
                )

    def volume_up(self):
        return self.change_volume(10)

    def volume_down(self):
        return self.change_volume(-10)

    def set_mute(self, muted):
        with self.volume_session() as volume:
            if volume is None:
                return (
                    "Volume support is not installed. Run: "
                    "python -m pip install pycaw"
                )

            try:
                volume.SetMute(1 if muted else 0, None)
            except Exception as error:
                print(f"[VOLUME MUTE ERROR] {error}")
                return "Could not change the system mute state."

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