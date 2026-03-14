#!/usr/bin/env python3
import enchant
from pynput import keyboard
import time
import sys # Import sys for exit on error
import json # <-- Import the json module
import subprocess # For AppleScript layout switching
import os # For path manipulations

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

        # --- MODIFIED SECTION START ---
        # Load mapping from JSON file
        mapping_file_path = "conversion_map.json"
        try:
            # Use utf-8 encoding for compatibility with Hebrew characters
            with open(mapping_file_path, 'r', encoding='utf-8') as f:
                self.en_to_he_mapping = json.load(f)
            print(f"Successfully loaded mapping from {mapping_file_path}")
        except FileNotFoundError:
            print(f"Error: Mapping file '{mapping_file_path}' not found.")
            print("Please create this file in the same directory as the script,")
            print("containing the English-to-Hebrew character mappings in JSON format.")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from '{mapping_file_path}'.")
            print("Please ensure the file contains valid JSON.")
            sys.exit(1)
        except Exception as e: # Catch other potential file reading errors
            print(f"An unexpected error occurred while reading '{mapping_file_path}': {e}")
            sys.exit(1)

        # Hebrew to English character mapping (reverse mapping - calculated after loading)
        # We prioritize lowercase English keys to avoid converting Hebrew into non-dictionary words (e.g. 'ApPle')
        self.he_to_en_mapping = {}
        for k, v in self.en_to_he_mapping.items():
            if v in self.he_to_en_mapping:
                if k.islower() and not self.he_to_en_mapping[v].islower():
                    self.he_to_en_mapping[v] = k
            else:
                self.he_to_en_mapping[v] = k
        # --- MODIFIED SECTION END ---


        self.controller = keyboard.Controller()
        self.typing_programmatically = False  # Flag to ignore programmatic typing
        self.word_processed_in_sentence = False # Only check the first word


    def on_press(self, key):
        """Handle key press events."""
        if self.typing_programmatically:
            return  # Ignore programmatically typed keys

        # Exit on Escape key
        if key == keyboard.Key.esc:
            print("Exiting...")
            return False  # Stop listener and exit program

        try:
            # Trigger process on space or punctuation
            if key == keyboard.Key.space or (hasattr(key, 'char') and key.char in ".,?!"):
                trigger = ' ' if key == keyboard.Key.space else key.char
                if self.current_word and not self.word_processed_in_sentence:
                    self.process_word(trigger)
                    self.word_processed_in_sentence = True
                self.current_word = "" # Reset word after trigger
                self.current_layout = None # Reset layout detection for next word
            elif key == keyboard.Key.enter:
                if self.current_word and not self.word_processed_in_sentence:
                    self.process_word('\n')
                self.word_processed_in_sentence = False # Reset for NEW sentence
                self.current_layout = None
                self.current_word = ""
            elif key == keyboard.Key.backspace:
                 if self.current_word:
                     self.current_word = self.current_word[:-1]
            elif hasattr(key, 'char') and key.char is not None:
                char = key.char
                self.current_word += char
                # Update layout based on the first alphabetical char typed
                if self.current_layout is None:
                    self.update_layout(char.lower())

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

    def process_word(self, trigger_char):
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
                # Use .get(c.lower(), c) to handle potential missing keys gracefully
                converted_to_he = ''.join(self.en_to_he_mapping.get(c.lower(), c) for c in word_to_process)
                print(f"Rule 3 (KB=En, Lang=He?): '{word_to_process}' -> '{converted_to_he}' - Converting to Hebrew")
                self.replace_and_switch("He", word_to_process, converted_to_he, trigger_char)
        elif self.current_layout == "He":
            # Rule 4: Assume Hebrew keys used for English word
            # Use .get(c, c) to handle potential missing keys gracefully
            converted_to_en = ''.join(self.he_to_en_mapping.get(c, c) for c in word_to_process) # Use original case for He mapping keys
            print(f"Checking if '{word_to_process}' is actually English (converted: '{converted_to_en}')")
            if self.is_english(converted_to_en):
                print(f"Rule 4 (KB=He, Lang=En?): '{word_to_process}' -> '{converted_to_en}' - Converting to English")
                self.replace_and_switch("En", word_to_process, converted_to_en, trigger_char)
            else:
                # Rule 2: Assume Hebrew keys used for Hebrew word (or unrecognized)
                print(f"Rule 2 (KB=He, Lang=He?): '{word_to_process}' - No change (converted '{converted_to_en}' not deemed English)")
                return

    # --- THIS FUNCTION IS MODIFIED ---
    def replace_and_switch(self, target_layout, original_word, corrected_word, trigger_char):
        """Replace the typed word and switch keyboard layout."""
        print(f"Action: Replacing '{original_word}' with '{corrected_word}', switching to {target_layout}")

        # Set flag to ignore the keys we are about to simulate
        self.typing_programmatically = True

        try:
            # Small delay before starting actions might help ensure focus
            time.sleep(0.05)

            # Simulate backspaces to delete the original typed word + triggering char
            num_backspaces = len(original_word) + 1
            for _ in range(num_backspaces):
                self.controller.press(keyboard.Key.backspace)
                self.controller.release(keyboard.Key.backspace)
                time.sleep(0.03) 

            # Switch layout
            self.switch_layout()

            # Wait for OS to process the change
            time.sleep(0.6)

            # Type the corrected word + trigger
            full_corrected = corrected_word + trigger_char
            print(f"Typing corrected word: '{full_corrected}'")
            self.controller.type(full_corrected)

            # Important: Update internal layout state AFTER switch and typing
            self.current_layout = target_layout
            
        finally:
            # Always ensure we stop ignoring keys
            time.sleep(0.05)
            self.typing_programmatically = False
            print(f"Correction complete. Target layout is {target_layout}")


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
        """
        if not word or len(word) < 2: return False 
        word_lower = word.lower() 

        # Strict check for very short words
        if len(word_lower) <= 3:
            return self.enchant_dict_en.check(word_lower)

        if self.enchant_dict_en.check(word_lower):
            return True
        
        suggestions = self.enchant_dict_en.suggest(word_lower)
        for sugg in suggestions:
            if self.levenshtein_distance(word_lower, sugg) < 2:
                return True
        return False

    # --- THIS FUNCTION IS ROBUST (v3 Swift Binary) ---
    def switch_layout(self):
        """Switch the keyboard layout using compiled Swift utility (Carbon TIS)."""
        print(f"Action: Attempting layout switch (Swift/Carbon TIS)")
        
        # Path to the compiled switcher
        current_dir = os.path.dirname(os.path.abspath(__file__))
        switcher_path = os.path.join(current_dir, "switch_layout")

        if os.path.exists(switcher_path):
            try:
                subprocess.run([switcher_path], check=True, capture_output=True, text=True)
                print("Layout switch triggered via Swift binary")
                return
            except Exception as e:
                print(f"Swift binary switch failed: {e}. Falling back to AppleScript.")
        else:
            print(f"Swift binary not found at {switcher_path}. Falling back to AppleScript.")

        # Method 2: AppleScript (Fallback)
        applescript = 'tell application "System Events" to key code 49 using control down'
        try:
            subprocess.run(['osascript', '-e', applescript], check=True)
            print("Layout switch triggered via AppleScript fallback")
        except Exception as e:
            print(f"AppleScript fallback failed: {e}. Falling back to pynput.")
            try:
                with self.controller.pressed(keyboard.Key.ctrl):
                    self.controller.press(keyboard.Key.space)
                    self.controller.release(keyboard.Key.space)
                print("Layout switch triggered via pynput simulation")
            except Exception as e2:
                print(f"All switch methods failed: {e2}")


def main():
    """Start the keyboard listener."""
    print("Starting Automatic Language Conversion (v7 - First Word Only) ...")
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
