import base64
import queue
import re
import subprocess
import threading
import time
from collections.abc import Callable

import speech_recognition as sr


class VoiceAssistant:
    """
    Hands-free voice controller for MV.AI.

    Current MVP behavior:
    - Continuously listens in a background thread.
    - Detects phrases such as "Hey MV".
    - Accepts a command in the same sentence or the next sentence.
    - Sends recognized commands to the desktop UI.
    - Speaks responses using Windows text-to-speech.
    """

    WAKE_PHRASES = (
        "hey mv",
        "hi mv",
        "okay mv",
        "ok mv",
        "hello mv",
    )

    def __init__(
        self,
        command_callback: Callable[[str], None],
        status_callback: Callable[[str], None] | None = None,
        message_callback: Callable[[str], None] | None = None,
    ):
        self.command_callback = command_callback
        self.status_callback = status_callback
        self.message_callback = message_callback

        self.recognizer = sr.Recognizer()

        # Useful starting values for normal room noise.
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 300
        self.recognizer.pause_threshold = 0.7
        self.recognizer.non_speaking_duration = 0.4

        self.microphone = None

        self.running_event = threading.Event()
        self.speaking_event = threading.Event()
        self.awake_event = threading.Event()

        self.listener_thread: threading.Thread | None = None
        self.speech_thread: threading.Thread | None = None

        self.speech_queue: queue.Queue[str | None] = queue.Queue()

        # Track the active Windows speech process so it can be stopped
        # cleanly if SAPI hangs or voice mode is turned off.
        self._speech_process: subprocess.Popen | None = None
        self._speech_process_lock = threading.RLock()

        self.awake_until = 0.0
        self.command_timeout_seconds = 8

    # --------------------------------------------------
    # Starting and stopping
    # --------------------------------------------------

    def start(self) -> bool:
        """
        Start microphone listening and speech output.
        """

        if self.running_event.is_set():
            return True

        try:
            self.microphone = sr.Microphone()

        except Exception as error:
            self.send_message(
                f"Microphone could not be started: {error}"
            )
            self.set_status("Voice error")
            return False

        self.running_event.set()

        self.speech_thread = threading.Thread(
            target=self.speech_worker,
            daemon=True,
            name="MV-Speech",
        )

        self.listener_thread = threading.Thread(
            target=self.listener_worker,
            daemon=True,
            name="MV-Listener",
        )

        self.speech_thread.start()
        self.listener_thread.start()

        self.set_status("Calibrating microphone")

        return True

    def stop(self) -> None:
        """
        Stop voice recognition and text-to-speech.
        """

        self.running_event.clear()
        self.awake_event.clear()
        self.cancel_current_speech()

        # Stop the speech worker.
        self.speech_queue.put(None)

    # --------------------------------------------------
    # Microphone listening
    # --------------------------------------------------

    def listener_worker(self) -> None:
        """
        Continuously listen for the wake phrase.
        """

        if self.microphone is None:
            return

        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(
                    source,
                    duration=1,
                )

            self.set_status("Listening for Hey MV")
            self.send_message(
                'Voice mode enabled. Say "Hey MV" to wake me.'
            )

        except Exception as error:
            self.set_status("Voice error")
            self.send_message(
                f"Microphone calibration failed: {error}"
            )
            return

        while self.running_event.is_set():
            if self.speaking_event.is_set():
                time.sleep(0.1)
                continue

            try:
                with self.microphone as source:
                    audio = self.recognizer.listen(
                        source,
                        timeout=1,
                        phrase_time_limit=5,
                    )

            except sr.WaitTimeoutError:
                self.check_awake_timeout()
                continue

            except Exception as error:
                self.send_message(
                    f"Microphone listening error: {error}"
                )
                time.sleep(1)
                continue

            if self.speaking_event.is_set():
                continue

            self.recognize_audio(audio)

    def recognize_audio(
        self,
        audio: sr.AudioData,
    ) -> None:
        """
        Convert captured speech to text.
        """

        try:
            text = self.recognizer.recognize_google(
                audio,
                language="en-IN",
            )

        except sr.UnknownValueError:
            return

        except sr.RequestError as error:
            self.set_status("Speech service unavailable")
            self.send_message(
                f"Speech recognition service error: {error}"
            )
            return

        except Exception as error:
            self.send_message(
                f"Speech recognition failed: {error}"
            )
            return

        normalized_text = self.normalize_text(text)

        if not normalized_text:
            return

        self.process_recognized_text(normalized_text)

    # --------------------------------------------------
    # Wake phrase logic
    # --------------------------------------------------

    def process_recognized_text(
        self,
        text: str,
    ) -> None:
        """
        Detect the wake phrase or process an active command.
        """

        wake_phrase = self.find_wake_phrase(text)

        if wake_phrase:
            command = self.extract_command(
                text,
                wake_phrase,
            )

            self.wake_up()

            if command:
                self.submit_command(command)

            else:
                self.speak("Yes?")
                self.set_status("Waiting for command")

            return

        if self.awake_event.is_set():
            if time.monotonic() <= self.awake_until:
                self.submit_command(text)
            else:
                self.sleep_mode()

    def wake_up(self) -> None:
        self.awake_event.set()

        self.awake_until = (
            time.monotonic()
            + self.command_timeout_seconds
        )

        self.set_status("Awake")

    def sleep_mode(self) -> None:
        self.awake_event.clear()
        self.awake_until = 0.0

        self.set_status("Listening for Hey MV")

    def check_awake_timeout(self) -> None:
        if not self.awake_event.is_set():
            return

        if time.monotonic() > self.awake_until:
            self.sleep_mode()

    def submit_command(
        self,
        command: str,
    ) -> None:
        command = command.strip(" ,.!?")

        if not command:
            return

        self.sleep_mode()
        self.set_status("Processing voice command")

        try:
            self.command_callback(command)

        except Exception as error:
            self.send_message(
                f"Could not submit voice command: {error}"
            )

    def find_wake_phrase(
        self,
        text: str,
    ) -> str | None:
        for wake_phrase in self.WAKE_PHRASES:
            if wake_phrase in text:
                return wake_phrase

        return None

    @staticmethod
    def extract_command(
        text: str,
        wake_phrase: str,
    ) -> str:
        wake_position = text.find(wake_phrase)

        if wake_position == -1:
            return ""

        command_start = (
            wake_position
            + len(wake_phrase)
        )

        command = text[command_start:]

        return command.strip(" ,.!?")

    @staticmethod
    def normalize_text(
        text: str,
    ) -> str:
        normalized = text.lower().strip()

        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        # Recognition may occasionally hear "MV" as separate letters.
        replacements = {
            "m v": "mv",
            "m. v.": "mv",
            "em vee": "mv",
            "mv ai": "mv",
        }

        for original, replacement in replacements.items():
            normalized = normalized.replace(
                original,
                replacement,
            )

        return normalized

    # --------------------------------------------------
    # Text-to-speech
    # --------------------------------------------------

    def speak(
        self,
        text: str,
    ) -> None:
        """
        Queue text for speech without freezing the UI.
        """

        clean_text = str(text).strip()

        if not clean_text:
            return

        print(f"[VOICE] Queued: {clean_text}")
        self.speech_queue.put(clean_text)

    def speech_worker(self) -> None:
        """
        Speak queued text using Windows PowerShell speech.

        A fresh Windows speech process is used for every response.
        This avoids the common pyttsx3/SAPI5 bug where only the
        first queued response is spoken.
        """

        print("[VOICE] Speech worker started")

        while True:
            try:
                text = self.speech_queue.get(
                    timeout=0.5
                )

            except queue.Empty:
                if not self.running_event.is_set():
                    break

                continue

            if text is None:
                self.speech_queue.task_done()
                break

            self.speaking_event.set()
            self.set_status("Speaking")

            try:
                print(f"[VOICE] Speaking: {text}")
                self.speak_with_windows(text)
                print("[VOICE] Finished speaking")

            except Exception as error:
                print(f"[VOICE ERROR] {error}")
                self.send_message(
                    f"Speech output failed and was reset: {error}"
                )

            finally:
                self.speaking_event.clear()
                self.speech_queue.task_done()

                # Never leave MV.ai stuck in speaking/error mode.
                if self.running_event.is_set():
                    self.set_status("Listening for Hey MV")

        print("[VOICE] Speech worker stopped")

    def cancel_current_speech(self) -> None:
        """Stop a hung Windows speech process, if one exists."""

        with self._speech_process_lock:
            process = self._speech_process

        if process is None or process.poll() is not None:
            return

        try:
            process.kill()
            process.communicate(timeout=2)
        except Exception:
            pass

    def speak_with_windows(
        self,
        text: str,
    ) -> None:
        """
        Speak one message with Windows System.Speech.

        The PowerShell process has a strict timeout and is forcibly reset
        if Windows SAPI speaks part of a sentence but never exits.
        """

        encoded_text = base64.b64encode(
            text.encode("utf-8")
        ).decode("ascii")

        powershell_script = (
            "Add-Type -AssemblyName System.Speech; "
            "$voice = New-Object "
            "System.Speech.Synthesis.SpeechSynthesizer; "
            "$voice.Rate = 1; "
            "$voice.Volume = 100; "
            f"$bytes = [Convert]::FromBase64String('{encoded_text}'); "
            "$text = [Text.Encoding]::UTF8.GetString($bytes); "
            "$voice.SpeakAsync($text) | Out-Null; "
            "$timer = [Diagnostics.Stopwatch]::StartNew(); "
            "while ($voice.State -eq [System.Speech.Synthesis.SynthesizerState]::Speaking -and "
            "$timer.Elapsed.TotalSeconds -lt 25) { "
            "Start-Sleep -Milliseconds 100 }; "
            "if ($voice.State -eq [System.Speech.Synthesis.SynthesizerState]::Speaking) { "
            "$voice.SpeakAsyncCancelAll(); "
            "$voice.Dispose(); "
            "[Console]::Error.WriteLine('Windows speech timed out.'); "
            "exit 2 }; "
            "$voice.Dispose();"
        )

        creation_flags = getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )

        process = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                powershell_script,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creation_flags,
        )

        with self._speech_process_lock:
            self._speech_process = process

        # Allow enough time for a normal short reply, but never let a
        # broken SAPI process block the voice worker indefinitely.
        timeout_seconds = min(35.0, max(12.0, 6.0 + len(text) / 10.0))

        try:
            stdout, stderr = process.communicate(
                timeout=timeout_seconds
            )
        except subprocess.TimeoutExpired as error:
            process.kill()
            stdout, stderr = process.communicate()
            raise RuntimeError(
                "Windows speech timed out and was automatically reset."
            ) from error
        finally:
            with self._speech_process_lock:
                if self._speech_process is process:
                    self._speech_process = None

        if process.returncode != 0:
            error_text = (
                (stderr or "").strip()
                or (stdout or "").strip()
                or "Windows speech stopped before finishing."
            )
            raise RuntimeError(error_text)

    # --------------------------------------------------
    # UI callbacks
    # --------------------------------------------------

    def set_status(
        self,
        status: str,
    ) -> None:
        if callable(self.status_callback):
            self.status_callback(status)

    def send_message(
        self,
        message: str,
    ) -> None:
        if callable(self.message_callback):
            self.message_callback(message)