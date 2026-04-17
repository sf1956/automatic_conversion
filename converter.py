"""
converter.py — Pure character-set conversion logic.

Loads the en↔he mapping from conversion_map.json and exposes:
  - detect_layout(word)  → "en" | "he" | None
  - en_to_hebrew(word)   → str
  - he_to_english(word)  → str

No I/O, no side effects, fully unit-testable.
"""
import json
from config import CONVERSION_MAP_PATH


class Converter:
    def __init__(self) -> None:
        with open(CONVERSION_MAP_PATH, "r", encoding="utf-8") as fh:
            self.en_to_he: dict[str, str] = json.load(fh)

        # Reverse map: Hebrew char → English char.
        # When both uppercase and lowercase English keys map to the same Hebrew
        # character, prefer the lowercase key (produces cleaner English output).
        self.he_to_en: dict[str, str] = {}
        for en_char, he_char in self.en_to_he.items():
            existing = self.he_to_en.get(he_char)
            if existing is None or (en_char.islower() and not existing.islower()):
                self.he_to_en[he_char] = en_char

    # ── Layout detection ─────────────────────────────────────────────────────

    def detect_layout(self, word: str) -> str | None:
        """
        Count Latin vs Hebrew characters and return the dominant script.

        Returns:
            "en"  — majority of recognisable characters are Latin (a–z)
            "he"  — majority are Hebrew (U+05D0–U+05EA)
            None  — word contains neither (digits, symbols only)
        """
        en_count = sum(1 for c in word if "a" <= c.lower() <= "z")
        he_count = sum(1 for c in word if "\u05d0" <= c <= "\u05ea")

        if en_count == 0 and he_count == 0:
            return None
        return "en" if en_count >= he_count else "he"

    # ── Conversion ───────────────────────────────────────────────────────────

    def en_to_hebrew(self, word: str) -> str:
        """
        Convert each English character to its Hebrew keyboard equivalent.
        Uses lowercase lookup so 'A' and 'a' both map to the same Hebrew char.
        Characters not in the map are passed through unchanged.
        """
        return "".join(self.en_to_he.get(c.lower(), c) for c in word)

    def he_to_english(self, word: str) -> str:
        """
        Convert each Hebrew character to its English keyboard equivalent.
        Characters not in the map are passed through unchanged.
        """
        return "".join(self.he_to_en.get(c, c) for c in word)
