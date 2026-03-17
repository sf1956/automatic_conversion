#!/usr/bin/env python3
import enchant
from pynput import keyboard
import time
import sys # Import sys for exit on error
import json # <-- Import the json module
import subprocess # For AppleScript layout switching
import os # For path manipulations
import threading
from PIL import Image, ImageDraw
import pystray
try:
    from ApplicationServices import AXIsProcessTrusted
except ImportError:
    AXIsProcessTrusted = None

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def get_macos_clipboard():
    """Get content from macOS clipboard using pbpaste."""
    try:
        result = subprocess.run(['pbpaste'], capture_output=True, text=True)
        return result.stdout
    except:
        return ""

def set_macos_clipboard(text):
    """Set content to macOS clipboard using pbcopy."""
    try:
        subprocess.run(['pbcopy'], input=text, text=True, check=True)
    except:
        pass

class LanguageLayoutManager:
    def __init__(self):
        # Setup logging to file immediately to catch all init steps
        self.log_file = os.path.expanduser("~/Library/Logs/LanguageSwitcher.log")
        try:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            # Standard write to clear/start fresh or append with clear separator
            with open(self.log_file, "a") as f:
                f.write(f"\n\n=== NEW SESSION: {time.strftime('%Y-%m-%d %H:%M:%S')} (v11) ===\n")
        except:
            pass

        self.log("Initializing LanguageLayoutManager...")
        
        # Initialize variables
        self.current_word = ""
        self.current_layout = None
        self.typing_programmatically = False
        self.word_processed_in_sentence = False
        
        # Dictionary for English
        try:
            self.enchant_dict_en = enchant.Dict("en_US")
            self.log("English dictionary loaded successfully.")
        except Exception as e:
            self.log(f"CRITICAL: Error loading English dictionary: {e}")
            sys.exit(1)

        # Load character mapping from JSON
        mapping_file = get_resource_path("conversion_map.json")
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                self.en_to_he_mapping = json.load(f)
            self.log(f"Successfully loaded mapping from {mapping_file}")
        except Exception as e:
            self.log(f"CRITICAL: Error loading conversion map from {mapping_file}: {e}")
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
        
        # Setup logging to file for bundled app debugging
        self.log_file = os.path.expanduser("~/Library/Logs/LanguageSwitcher.log")
        try:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            with open(self.log_file, "a") as f:
                f.write(f"\n--- App Started: {time.ctime()} ---\n")
        except:
            pass

    def log(self, message):
        """Log message to console and file."""
        print(message)
        try:
            with open(self.log_file, "a") as f:
                f.write(f"{time.strftime('%H:%M:%S')} - {message}\n")
        except:
            pass

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
            if key == keyboard.Key.space or (hasattr(key, 'char') and key.char is not None and key.char in ".,?!"):
                trigger = ' ' if key == keyboard.Key.space else key.char
                if self.current_word and not self.word_processed_in_sentence:
                    # LOCK IMMEDIATELY to prevent interleaving
                    self.word_processed_in_sentence = True
                    self.process_word(trigger)
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

        except Exception as e:
            self.log(f"Error in on_press: {e}")

    def detect_dominant_layout(self, word):
        """Determine the current keyboard layout based on the majority of characters."""
        en_count = 0
        he_count = 0
        for char in word:
            char_lower = char.lower()
            if 'a' <= char_lower <= 'z':
                en_count += 1
            elif '\u05d0' <= char_lower <= '\u05ea':  # Hebrew Unicode range
                he_count += 1
        
        if en_count == 0 and he_count == 0:
            return None
            
        if en_count >= he_count:
            self.log(f"Dominant Layout detected: En ({en_count} En vs {he_count} He)")
            return "En"
        else:
            self.log(f"Dominant Layout detected: He ({he_count} He vs {en_count} En)")
            return "He"

    def process_word(self, trigger_char):
        """Process the typed word and apply the rules."""
        # Detect dominant layout for the whole word
        self.current_layout = self.detect_dominant_layout(self.current_word)
        
        if not self.current_layout or not self.current_word:
            self.log(f"Skipping processing: Layout={self.current_layout}, Word='{self.current_word}'")
            return  # No layout determined yet or word is empty

        word_to_process = self.current_word # Keep a copy before it's reset
        self.log(f"\nProcessing word: '{word_to_process}' with detected layout: {self.current_layout}")

        # Detect language and apply rules
        if self.current_layout == "En":
            if self.is_english(word_to_process):
                self.log(f"Rule 1 (KB=En, Lang=En): '{word_to_process}' - No change")
                return
            else:
                # Rule 3: Assume English keys used for Hebrew word
                # Use .get(c.lower(), c) to handle potential missing keys gracefully
                converted_to_he = ''.join(self.en_to_he_mapping.get(c.lower(), c) for c in word_to_process)
                self.log(f"Rule 3 (KB=En, Lang=He?): '{word_to_process}' -> '{converted_to_he}' - Converting to Hebrew")
                self.replace_and_switch("He", word_to_process, converted_to_he, trigger_char)
        elif self.current_layout == "He":
            # Rule 4: Assume Hebrew keys used for English word
            # Use .get(c, c) to handle potential missing keys gracefully
            converted_to_en = ''.join(self.he_to_en_mapping.get(c, c) for c in word_to_process) # Use original case for He mapping keys
            self.log(f"Checking if '{word_to_process}' is actually English (converted: '{converted_to_en}')")
            if self.is_english(converted_to_en):
                self.log(f"Rule 4 (KB=He, Lang=En?): '{word_to_process}' -> '{converted_to_en}' - Converting to English")
                self.replace_and_switch("En", word_to_process, converted_to_en, trigger_char)
            else:
                # Rule 2: Assume Hebrew keys used for Hebrew word (or unrecognized)
                self.log(f"Rule 2 (KB=He, Lang=He?): '{word_to_process}' - No change (converted '{converted_to_en}' not deemed English)")
                return

    # --- THIS FUNCTION IS MODIFIED (v16 Deferred Switch) ---
    def replace_and_switch(self, target_layout, original_word, corrected_word, trigger_char):
        """Replace the typed word and switch keyboard layout."""
        self.log(f"Action: Replacing '{original_word}' with '{corrected_word}', switching to {target_layout}")

        # Set flag to ignore the keys we are about to simulate
        self.typing_programmatically = True

        # 1. Save current clipboard
        original_clipboard = get_macos_clipboard()

        try:
            # 2. Backspace the original word + trigger char
            num_backspaces = len(original_word) + 1
            for _ in range(num_backspaces):
                self.controller.press(keyboard.Key.backspace)
                self.controller.release(keyboard.Key.backspace)
            
            # 3. Paste the corrected word + trigger IMMEDIATELY
            # Paste works regardless of layout, so we do it first to avoid the switch delay
            full_to_paste = corrected_word + trigger_char
            set_macos_clipboard(full_to_paste)
            
            # Simulate Cmd+V
            with self.controller.pressed(keyboard.Key.cmd):
                self.controller.press('v')
                self.controller.release('v')
            
            self.log(f"Pasted corrected word: '{full_to_paste}'")

            # 4. NOW switch layout for future typing
            self.switch_layout()

            # 5. Settle time for the layout switch to take effect
            time.sleep(0.4)

            # Important: Update internal layout state AFTER switch
            self.current_layout = target_layout
            
        finally:
            # 6. Restore original clipboard
            set_macos_clipboard(original_clipboard)
            
            # Always ensure we stop ignoring keys
            self.typing_programmatically = False
            self.log(f"Correction complete. Target layout is {target_layout}")


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
        self.log(f"Action: Attempting layout switch (Swift/Carbon TIS)")
        
        # Path to the compiled switcher
        switcher_path = get_resource_path("switch_layout")

        if os.path.exists(switcher_path):
            try:
                subprocess.run([switcher_path], check=True, capture_output=True, text=True)
                self.log("Layout switch triggered via Swift binary")
                return
            except Exception as e:
                self.log(f"Swift binary switch failed: {e}. Falling back to AppleScript.")
        else:
            self.log(f"Swift binary not found at {switcher_path}. Falling back to AppleScript.")

        # Method 2: AppleScript (Fallback)
        applescript = 'tell application "System Events" to key code 49 using control down'
        try:
            subprocess.run(['osascript', '-e', applescript], check=True)
            self.log("Layout switch triggered via AppleScript fallback")
        except Exception as e:
            self.log(f"AppleScript fallback failed: {e}. Falling back to pynput.")
            try:
                with self.controller.pressed(keyboard.Key.ctrl):
                    self.controller.press(keyboard.Key.space)
                    self.controller.release(keyboard.Key.space)
                self.log("Layout switch triggered via pynput simulation")
            except Exception as e2:
                self.log(f"All switch methods failed: {e2}")


def create_image():
    # Load the application icon from resources
    icon_path = get_resource_path("icon.icns")
    if os.path.exists(icon_path):
        try:
            return Image.open(icon_path)
        except Exception as e:
            print(f"Error loading icon image: {e}")
    
    # Fallback to generated image if icon.icns is missing or fails
    width = 64
    height = 64
    color1 = "blue"
    color2 = "white"
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.text((10, 10), "HE/EN", fill=color2)
    return image

def on_quit(icon, item):
    icon.stop()
    os._exit(0)

def main():
    """Start the keyboard listener and tray icon."""
    print("Starting Automatic Language Conversion (v17 - Punctuation Fix) ...")
    
    manager = LanguageLayoutManager()
    
    # Check for Accessibility permissions
    if AXIsProcessTrusted is not None:
        trusted = AXIsProcessTrusted()
        manager.log(f"Accessibility Permission (AXIsProcessTrusted): {trusted}")
        if not trusted:
            manager.log("WARNING: App does NOT have Accessibility permissions. Keyboard replacement will fail.")
    else:
        manager.log("Could not check Accessibility permissions (ApplicationServices not found).")

    # Start the keyboard listener in a non-blocking daemon thread
    listener = keyboard.Listener(on_press=manager.on_press)
    listener.daemon = True
    listener.start()
    
    # Create and run the tray icon (blocking)
    icon = pystray.Icon("LangSwitcher", create_image(), "Language Switcher", 
                        menu=pystray.Menu(pystray.MenuItem("Quit", on_quit)))
    icon.run()


if __name__ == "__main__":
    main()
