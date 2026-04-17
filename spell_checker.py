"""
spell_checker.py — English word validation.

Wraps pyenchant with a stricter fuzzy-match policy to reduce false positives:
  - Short words (≤ 3 chars): exact dictionary match only.
  - Longer words: allow edit distance == 1 ONLY when the candidate starts with
    the same letter (prevents "asf" → "as" triggering "is English").

The Levenshtein helper is self-contained; no external library required.
"""
import logging
from config import SPELL_SUGGEST_LIMIT

log = logging.getLogger(__name__)


class SpellChecker:
    def __init__(self, lang: str = "en_US") -> None:
        try:
            import enchant
            self._dict = enchant.Dict(lang)
            log.info(f"SpellChecker: loaded '{lang}' dictionary via pyenchant")
        except Exception as exc:
            log.critical(f"SpellChecker: failed to load dictionary — {exc}")
            raise

    # ── Public API ────────────────────────────────────────────────────────────

    # Single-character words that are valid English.
    # These MUST be accepted or they'll trigger a false layout switch.
    _SINGLE_CHAR_WORDS = frozenset({"i", "a"})

    def is_english(self, word: str) -> bool:
        """
        Return True if *word* is a plausible English word.

        Detection rules:
          1. Empty words return False.
          2. Single characters: only 'I' and 'a' are accepted (the only
             single-letter English words). Without this, typing "I" on an
             English layout triggers Rule 3 → converts to Hebrew → flips
             the layout back, causing the back-and-forth bug.
          3. Words ≤ 3 chars must be an exact dictionary hit.
          4. Longer words: exact hit OR one suggestion within edit-distance 1
             that shares the same first letter.
        """
        if not word:
            return False

        w = word.lower()

        # Single character: whitelist only.
        if len(w) == 1:
            return w in self._SINGLE_CHAR_WORDS

        # Short words (2-3 chars): strict dictionary match only.
        if len(w) <= 3:
            return self._dict.check(w)

        # Exact match.
        if self._dict.check(w):
            return True

        # Fuzzy match: consider top suggestions.
        for suggestion in self._dict.suggest(w)[:SPELL_SUGGEST_LIMIT]:
            s = suggestion.lower()
            # Same first letter guard prevents cross-word false positives.
            if s and s[0] == w[0] and self._levenshtein(w, s) == 1:
                return True

        return False

    # ── Internal helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _levenshtein(s: str, t: str) -> int:
        """Standard dynamic-programming Levenshtein edit distance."""
        m, n = len(s), len(t)
        if m == 0:
            return n
        if n == 0:
            return m

        # Early exit optimisation: if lengths differ by more than 1 the
        # distance is at least 1 — caller checks == 1, so this is still valid.
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                cost = 0 if s[i - 1] == t[j - 1] else 1
                dp[i][j] = min(
                    dp[i - 1][j] + 1,        # deletion
                    dp[i][j - 1] + 1,        # insertion
                    dp[i - 1][j - 1] + cost, # substitution
                )
        return dp[m][n]
