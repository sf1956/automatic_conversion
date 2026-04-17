"""
keyboard_replacer.py — Erases a mis-typed word and inserts the corrected one.

Replacement strategy: clipboard paste (Cmd+V)
──────────────────────────────────────────────
Clipboard paste is used instead of controller.type() because:

1. It is layout-independent: pasting "hello" always inserts "hello" regardless
   of whether the active input source is English or Hebrew.

2. It is atomic: the entire corrected word appears at once, not character by
   character.  This shrinks the time window between "backspace" and "text
   appears" to near-zero, preventing the fast-typing race condition where
   the first character of the user's next word lands between our backspace
   and our typed text.

Operation order:
  1. Save clipboard (text-only via pbpaste)
  2. Set clipboard to corrected_word + trigger (pbcopy)
  3. Backspace original word + trigger  (fast, ~ms)
  4. Cmd+V paste                        (fast, ~ms, layout-independent)
  5. Switch OS layout for future typing  (0.15 s delay — but text is already
     correct, so user keystrokes during this delay land AFTER the corrected
     word, which is the right position)
  6. Restore clipboard

Limitation: clipboard save/restore is text-only.  If the user had rich
content (images, files) on the clipboard it will be lost.  A future
improvement could use NSPasteboard via PyObjC to preserve all pasteboard
items.
"""
import logging
import os
import subprocess
import threading
import time

from pynput import keyboard as kb

from layout_switcher import LayoutSwitcher

log = logging.getLogger(__name__)


# ── Clipboard helpers ─────────────────────────────────────────────────────────

def _get_clipboard() -> str:
    """Read the current clipboard as plain text."""
    try:
        result = subprocess.run(
            ["pbpaste"], capture_output=True, text=True, timeout=2,
        )
        return result.stdout
    except Exception:
        return ""


def _set_clipboard(text: str) -> None:
    """Write plain text to the clipboard."""
    try:
        subprocess.run(
            ["pbcopy"], input=text, text=True, check=True, timeout=2,
        )
    except Exception as exc:
        log.warning(f"pbcopy failed: {exc}")


# ── Replacer ──────────────────────────────────────────────────────────────────

class KeyboardReplacer:
    def __init__(self, switcher: LayoutSwitcher) -> None:
        self._controller = kb.Controller()
        self._switcher   = switcher
        self._lock       = threading.Lock()
        self._pending    = 0   # synthetic key-press events still to suppress

    # ── Called from the listener thread ──────────────────────────────────────

    def consume_synthetic(self) -> bool:
        """
        Atomically check whether the next key-press event is one of ours.

        Returns True  → event is synthetic, caller should ignore it.
        Returns False → event is a real keypress, process normally.
        """
        with self._lock:
            if self._pending > 0:
                self._pending -= 1
                return True
        return False

    # ── Called from the worker thread ────────────────────────────────────────

    def replace(
        self,
        original: str,
        corrected: str,
        trigger: str,
        target_layout: str,
    ) -> None:
        """
        Erase *original* + *trigger* from the active text field, then paste
        *corrected* + *trigger* via the clipboard, and switch to
        *target_layout*.
        """
        n_backspaces = len(original) + 1   # +1 to erase the trigger

        # Synthetic event count:
        #   n_backspaces  (one on_press per backspace)
        # + 2             (Cmd key-down + 'v' key-down for Cmd+V)
        total_synthetic = n_backspaces + 2

        with self._lock:
            self._pending = total_synthetic

        log.info(
            f"Replacing '{original}' → '{corrected}' "
            f"(trigger={repr(trigger)}, {n_backspaces} bs, "
            f"{total_synthetic} synthetic events)"
        )

        # 1. Save current clipboard before we overwrite it.
        saved_clipboard = _get_clipboard()

        try:
            # 2. Load the corrected text into the clipboard.
            _set_clipboard(corrected + trigger)

            # 3. Erase the original word + trigger.
            #    Backspace works regardless of which layout is active.
            for _ in range(n_backspaces):
                self._controller.press(kb.Key.backspace)
                self._controller.release(kb.Key.backspace)

            # 4. Cmd+V paste — layout-independent, near-instant.
            #    No delay between backspace and paste, so there is no window
            #    for the user's next keystroke to land in the wrong position.
            with self._controller.pressed(kb.Key.cmd):
                self._controller.press("v")
                self._controller.release("v")

            # 5. Switch OS layout for future typing.
            #    This has a ~150 ms delay, but the corrected text is already
            #    on screen.  Any character the user types during this delay
            #    will appear AFTER the corrected word — the correct position.
            self._switcher.switch()

            # 6. Short drain for any in-flight listener events.
            time.sleep(0.05)

            log.info(f"Replacement complete → target layout: {target_layout}")

        except Exception as exc:
            log.error(f"KeyboardReplacer.replace failed: {exc}", exc_info=True)

        finally:
            # Safety net: reset pending so the listener is never permanently stuck.
            with self._lock:
                self._pending = 0

            # 7. Restore the user's original clipboard.
            if saved_clipboard:
                _set_clipboard(saved_clipboard)
