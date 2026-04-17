"""
layout_switcher.py — OS keyboard layout toggling.

Tries layout switch via three methods in priority order:
  1. Compiled Swift binary  (Carbon TIS — fastest, most reliable)
  2. AppleScript            (slower, but no binary required)
  3. pynput simulation      (last resort, Ctrl+Space shortcut)
"""
import logging
import os
import subprocess
import time

from pynput import keyboard as kb

from config import SWITCH_LAYOUT_BIN, LAYOUT_SWITCH_DELAY

log = logging.getLogger(__name__)


class LayoutSwitcher:
    def __init__(self) -> None:
        self._controller = kb.Controller()

    def switch(self) -> None:
        """Toggle the macOS keyboard layout and wait for it to settle."""
        if self._try_swift_binary():
            return
        if self._try_applescript():
            return
        self._try_pynput()

    # ── Private methods ───────────────────────────────────────────────────────

    def _try_swift_binary(self) -> bool:
        if not os.path.exists(SWITCH_LAYOUT_BIN):
            log.debug(f"Swift binary not found at {SWITCH_LAYOUT_BIN}")
            return False
        try:
            subprocess.run(
                [SWITCH_LAYOUT_BIN],
                check=True,
                capture_output=True,
                text=True,
            )
            log.debug("Layout switched via Swift binary")
            time.sleep(LAYOUT_SWITCH_DELAY)
            return True
        except Exception as exc:
            log.warning(f"Swift binary failed: {exc}")
            return False

    def _try_applescript(self) -> bool:
        script = 'tell application "System Events" to key code 49 using control down'
        try:
            subprocess.run(
                ["osascript", "-e", script],
                check=True,
                capture_output=True,
            )
            log.debug("Layout switched via AppleScript")
            time.sleep(LAYOUT_SWITCH_DELAY)
            return True
        except Exception as exc:
            log.warning(f"AppleScript failed: {exc}")
            return False

    def _try_pynput(self) -> None:
        try:
            with self._controller.pressed(kb.Key.ctrl):
                self._controller.press(kb.Key.space)
                self._controller.release(kb.Key.space)
            log.debug("Layout switched via pynput (Ctrl+Space)")
            time.sleep(LAYOUT_SWITCH_DELAY)
        except Exception as exc:
            log.error(f"All layout switch methods failed: {exc}")
