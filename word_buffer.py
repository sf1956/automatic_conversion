"""
word_buffer.py — Thread-safe character accumulator.

The pynput listener thread calls add()/backspace() on every keystroke.
The worker thread calls flush() when a word boundary is detected.
A threading.Lock ensures no data races between the two threads.
"""
import threading


class WordBuffer:
    """Accumulates individual keystrokes into a word, safe for concurrent access."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._chars: list[str] = []

    def add(self, char: str) -> None:
        """Append a single character to the current word."""
        with self._lock:
            self._chars.append(char)

    def backspace(self) -> None:
        """Remove the last character (mirrors a real Backspace press)."""
        with self._lock:
            if self._chars:
                self._chars.pop()

    def flush(self) -> str:
        """Return the accumulated word and reset the buffer to empty."""
        with self._lock:
            word = "".join(self._chars)
            self._chars.clear()
            return word

    def reset(self) -> None:
        """Discard the current word without returning it."""
        with self._lock:
            self._chars.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._chars)
