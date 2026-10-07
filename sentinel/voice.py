"""Spoken warnings from the street light's speaker, using the operating system's own text-to-speech.

macOS: `say` · Windows: System.Speech via PowerShell · Linux: `espeak` / `spd-say`.
Nothing to install; if no speech engine exists, warnings are silently skipped (and reported once).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import threading

log = logging.getLogger("sentinel.voice")

MODES = ("off", "high", "medium")  # medium = MEDIUM and HIGH


def speech_command(text: str, platform: str | None = None) -> list[str] | None:
    platform = platform or sys.platform
    if platform == "darwin":
        return ["say", text]
    if platform.startswith("win"):
        safe = text.replace("'", "''")  # PowerShell single-quoted string
        return ["powershell", "-NoProfile", "-Command",
                f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{safe}')"]
    for engine in ("espeak", "spd-say"):
        if shutil.which(engine):
            return [engine, text]
    return None


class Speaker:
    def __init__(self) -> None:
        self._busy = threading.Lock()
        self.available = speech_command("test") is not None
        self.last_error = ""

    def say(self, text: str) -> bool:
        """Speak in the background; skips if still speaking the previous warning."""
        command = speech_command(text)
        if command is None:
            self.last_error = "No text-to-speech engine found on this computer"
            return False
        if not self._busy.acquire(blocking=False):
            return False
        threading.Thread(target=self._run, args=(command,), name="voice", daemon=True).start()
        return True

    def _run(self, command: list[str]) -> None:
        try:
            subprocess.run(command, timeout=30, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.last_error = ""
        except (OSError, subprocess.SubprocessError) as error:
            self.last_error = str(error)
            log.warning("voice warning failed: %s", error)
        finally:
            self._busy.release()
