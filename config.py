"""
config.py — Shared configuration and resource path resolution.
Works in both development (plain Python) and PyInstaller bundles.
"""
import os
import sys


def get_resource_path(relative_path: str) -> str:
    """Resolve a resource path that works in both dev mode and PyInstaller bundles."""
    try:
        # PyInstaller unpacks files into a temp dir stored in sys._MEIPASS
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


# ── File paths ───────────────────────────────────────────────────────────────
LOG_FILE            = os.path.expanduser("~/Library/Logs/LanguageSwitcher.log")
CONVERSION_MAP_PATH = get_resource_path("conversion_map.json")
SWITCH_LAYOUT_BIN   = get_resource_path("switch_layout")
ICON_PATH           = get_resource_path("icon.icns")

# ── Tuning ───────────────────────────────────────────────────────────────────
# Seconds to wait after triggering an OS layout switch (lets the system settle)
LAYOUT_SWITCH_DELAY = 0.15

# Maximum number of enchant suggestions to check for fuzzy English matching
SPELL_SUGGEST_LIMIT = 5

# Characters that act as a "word boundary" and trigger processing
TRIGGER_SPACE  = " "
TRIGGER_ENTER  = "\n"
TRIGGER_PUNCT  = set(".,?!")
