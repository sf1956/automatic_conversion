#!/usr/bin/env python3
import enchant
from pynput import keyboard
import time
import sys # Import sys for exit on error

class LanguageLayoutManager:
    def __init__(self):
        # Initialize variables
        self.current_word = ""
        self.current_layout = None
        try:
            self.enchant_dict_en = enchant.Dict("en_US")
        except enchant.errors.DictNotFoundError:
            print("Error: English dictionary 'en_US' not found.")
            print("Please ensure enchant and the dictionary are installed.")
            print("On Ubuntu/Debian: sudo apt-get install myspell-en-us")
            print("On macOS (with brew): brew install enchant hunspell")
            sys.exit(1) # Exit if dictionary is missing

        self.controller = keyboard.Controller()
        self.typing_programmatically = False  # Flag to ignore programmatic typing
        self.first_word_processed = False  # Flag to track if the first word has been processed

        # English to Hebrew character mapping (simplified example)
        self.en_to_he_mapping = {
            'a': 'ש', 'b': 'נ', 'c': 'ב', 'd': 'ג', 'e': 'ק', 'f': 'כ', 'g': 'ע', 'h': 'י', 'i': 'ן',
            'j': 'ח', 'k': 'ל', 'l': 'ך', 'm': 'צ', 'n': 'מ', 'o': 'ם', 'p': 'פ', 'q': '/', 'r': 'ר',
            's': 'ד', 't': 'א', 'u': 'ו', 'v': 'ה', 'w': '׳', 'x': 'ס', 'y': 'ט', 'z': 'ז',
            ' ': ' ', ',': 'ת', '.': 'ץ',  # Preserve spaces and punctuation
            '0': '0', '1': '1', '2': '2', '3': '3', '4': '4',
            '5': '5', '6': '6', '7': '7', '8': '8', '9': '9'
        }

        # Hebrew to English character mapping (reverse mapping)
        self.he_to_en_mapping = {v: k for k, v in self.en_to_he_mapping.items()}

    def on_press(self, key):
        """Handle key press events."""
        if self.typing_programmatically:
            return  # Ignore programmatically typed keys

        # Exit on Escape key
        if key == keyboard.Key.esc:
            print("Exiting...")
            return False  # Stop listener and exit program

        try:
            if key == keyboard.Key.space:
                # Process word only if it hasn't been processed yet in this sequence
                if not self.first_word_processed and self.current_word:
                    self.process_word()
                self.first_word_processed = True # Mark as processed after first space
                self.current_word = "" # Reset word after space
            elif key == keyboard.Key.enter:
                # Optionally process word before clearing if needed, or just reset
                # if self.current_word: self.process_word()
                self.first_word_processed = False # Reset processing flag on new line
                self.current_layout = None # Reset layout detection on new line
                self.current_word = ""
            elif key == keyboard.Key.backspace:
                 if self.current_word:
                     self.current_word = self.current_word[:-1]
            elif hasattr(key, 'char') and key.char is not None:
                char = key.char # Keep original case for mapping if needed, but layout check uses lower
                self.current_word += char
                # Update layout based on the *first* char typed after Enter/start
                if not self.first_word_processed and self.current_layout is None:
                    self.update_layout(char.lower()) # Use lower for check

        except Exception as e:
            print(f"Error in on_press: {e}")
            # Consider logging traceback: import traceback; traceback.print_exc()

    def update_layout(self, char_lower):
        """Determine the current keyboard layout based on the character."""
        if 'a' <= char_lower <= 'z':
            self.current_layout = "En"
            print("Layout detected: En")
        elif '\u05d0' <= char_lower <= '\u05ea':  # Hebrew Unicode range
            self.current_layout = "He"
            print("Layout detected: He")
        # else: layout remains None if first char is symbol/number

    def process_word(self):
        """Process the typed word and apply the rules."""
        if not self.current_layout or not self.current_word:
            print("Skipping processing: No layout detected or empty word.")
            return  # No layout determined yet or word is empty

        word_to_process = self.current_word # Keep a copy before it's reset
        print(f"\nProcessing word: '{word_to_process}' with detected layout: {self.current_layout}")

        # Detect language and apply rules
        if self.current_layout == "En":
            if self.is_english(word_to_process):
                print(f"Rule 1 (KB=En, Lang=En): '{word_to_process}' - No change")
                return
            else:
                # Rule 3: Assume English keys used for Hebrew word
                converted_to_he = ''.join(self.en_to_he_mapping.get(c.lower(), c) for c in word_to_process)
                print(f"Rule 3 (KB=En, Lang=He?): '{word_to_process}' -> '{converted_to_he}' - Converting to Hebrew")
                self.replace_and_switch("He", word_to_process, converted_to_he)
        elif self.current_layout == "He":
            # Rule 4: Assume Hebrew keys used for English word
            converted_to_en = ''.join(self.he_to_en_mapping.get(c, c) for c in word_to_process) # Use original case for He mapping keys
            if self.is_english(converted_to_en):
                print(f"Rule 4 (KB=He, Lang=En?): '{word_to_process}' -> '{converted_to_en}' - Converting to English")
                self.replace_and_switch("En", word_to_process, converted_to_en)
            else:
                # Rule 2: Assume Hebrew keys used for Hebrew word (or unrecognized)
                print(f"Rule 2 (KB=He, Lang=He?): '{word_to_process}' - No change (converted '{converted_to_en}' not deemed English)")
                return

    # --- THIS FUNCTION IS MODIFIED ---
    def replace_and_switch(self, target_layout, original_word, corrected_word):
        """Replace the typed word, add a space, and switch keyboard layout."""
        print(f"Action: Replacing '{original_word}' with '{corrected_word}', switching to {target_layout}")

        # Set flag to ignore the keys we are about to simulate
        self.typing_programmatically = True

        # Small delay before starting actions might help ensure focus
        time.sleep(0.05)

        # Simulate backspaces to delete the original typed word + the triggering space
        num_backspaces = len(original_word) + 1
        for _ in range(num_backspaces):
            self.controller.press(keyboard.Key.backspace)
            self.controller.release(keyboard.Key.backspace)
            time.sleep(0.01) # Minimal delay between backspaces

        # *** FIX: Switch layout BEFORE typing ***
        self.switch_layout() # Just toggle the layout
        # *** FIX: Wait AFTER switching for OS to process the change ***
        time.sleep(0.15) # Increased delay slightly, adjust if needed

        # Type the corrected word followed by a space
        print(f"Typing corrected word: '{corrected_word}'")
        self.controller.type(corrected_word + ' ')

        # Short delay after actions before listening again
        time.sleep(0.05)
        self.typing_programmatically = False
        print(f"Correction complete. Target layout should be {target_layout}")
        # Update internal layout state AFTER switch and typing
        self.current_layout = target_layout


    def levenshtein_distance(self, s, t):
        """
        Calculate the Levenshtein edit distance between two strings s and t.
        """
        m, n = len(s), len(t)
        if m == 0: return n
        if n == 0: return m
        # Use python-Levenshtein if available (faster), otherwise fallback
        try:
            import Levenshtein
            return Levenshtein.distance(s, t)
        except ImportError:
            # Fallback to manual implementation if Levenshtein not installed
            dp = [[0] * (n + 1) for _ in range(m + 1)]
            for i in range(m + 1): dp[i][0] = i
            for j in range(n + 1): dp[0][j] = j
            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    cost = 0 if s[i - 1] == t[j - 1] else 1
                    dp[i][j] = min(dp[i - 1][j] + 1,      # deletion
                                 dp[i][j - 1] + 1,      # insertion
                                 dp[i - 1][j - 1] + cost) # substitution
            return dp[m][n]

    def is_english(self, word):
        """
        Check if a word is in English, allowing for small spelling mistakes.
        Uses Levenshtein distance for similarity check.
        """
        if not word: return False # Handle empty string case
        word_lower = word.lower() # Check dictionary with lowercase

        if self.enchant_dict_en.check(word_lower):
            return True
        suggestions = self.enchant_dict_en.suggest(word_lower)
        for sugg in suggestions:
            # Allow distance up to 1 for short words, 2 for longer ones maybe?
            # Using fixed < 2 for now as per original code.
            # Consider using python-Levenshtein for speed if installed
            if self.levenshtein_distance(word_lower, sugg) < 2:
                # print(f"'{word}' is close to suggestion '{sugg}'") # Debugging
                return True
        # print(f"'{word}' not found and no close suggestions.") # Debugging
        return False

    # --- THIS FUNCTION IS MODIFIED ---
    def switch_layout(self):
        """Switch the keyboard layout using Ctrl+Space (adjust shortcut if needed)."""
        # Assumes Ctrl+Space toggles between the layouts (e.g., En <-> He)
        print(f"Action: Simulating layout switch (Ctrl+Space)")
        try:
            self.controller.press(keyboard.Key.ctrl)
            self.controller.press(keyboard.Key.space)
            self.controller.release(keyboard.Key.space)
            self.controller.release(keyboard.Key.ctrl)
            # The necessary delay is handled *after* calling this function in replace_and_switch
        except Exception as e:
            print(f"Error simulating layout switch: {e}")
            # Ensure keys are released if error occurs mid-press
            try: self.controller.release(keyboard.Key.space)
            except: pass
            try: self.controller.release(keyboard.Key.ctrl)
            except: pass


def main():
    """Start the keyboard listener."""
    print("Starting Automatic Language Conversion...")
    print("Press ESC to exit.")
    manager = LanguageLayoutManager() # Handles dictionary loading checks in init
    with keyboard.Listener(on_press=manager.on_press) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            print("\nKeyboardInterrupt received. Exiting.")
        except Exception as e:
            print(f"\nAn unexpected error occurred in the listener: {e}")
            # import traceback; traceback.print_exc() # Uncomment for detailed debugging


if __name__ == "__main__":
    main()
