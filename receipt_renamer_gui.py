# receipt_renamer_gui.py

import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
import threading
import os
import sys

# Global variables to store user selections
selected_files_list = []
selected_output_dir = ""

# Import the core renaming logic and configuration
try:
    from receipt_renamer import process_receipts, config, log_file_path
except ImportError as e:
    messagebox.showerror("Import Error",
                         f"Could not import receipt_renamer.py. "
                         f"Please ensure it's in the same directory and all its dependencies are met.\nError: {e}")
    sys.exit(1)

# --- GUI Logic ---

# Helper function to append messages to the scrolledtext widget
def append_to_log(message, tag=None):
    root.after(0, _append_to_log_thread_safe, message, tag)

def _append_to_log_thread_safe(message, tag=None):
    log_text.configure(state="normal")
    log_text.insert(tk.END, message + "\n", tag)
    log_text.see(tk.END) # Auto-scroll to the end
    
    # Configure tags for different message types (e.g., errors in red)
    if not hasattr(log_text, '_tags_configured'): # Configure tags only once
        log_text.tag_configure("error", foreground="red", font=("Courier New", 9, "bold"))
        log_text.tag_configure("warning", foreground="yellow", font=("Courier New", 9, "bold"))
        log_text._tags_configured = True

    log_text.configure(state="disabled")

# Function to select multiple receipt files
def select_receipt_files():
    global selected_files_list
    # Default to the config.INPUT_FOLDER if it exists, otherwise the current directory
    initial_dir = os.path.abspath(config.INPUT_FOLDER) if os.path.exists(config.INPUT_FOLDER) else os.getcwd()
    
    filetypes = [
        ("Receipt Files", "*.pdf *.png *.jpg *.jpeg *.gif *.bmp *.tiff"),
        ("PDF documents", "*.pdf"),
        ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff"),
        ("All files", "*.*")
    ]
    files = filedialog.askopenfilenames(
        title="Select Receipt Files",
        initialdir=initial_dir,
        filetypes=filetypes
    )
    if files:
        selected_files_list = list(files)
        files_selected_label.config(text=f"Selected {len(selected_files_list)} file(s)")
        append_to_log(f"User selected {len(selected_files_list)} file(s).")
    else:
        selected_files_list = []
        files_selected_label.config(text="No files selected.")
        append_to_log("File selection cancelled.")
    update_run_button_state()

# Function to select the output destination folder
def select_output_destination():
    global selected_output_dir
    # Default to the config.OUTPUT_FOLDER if it exists, otherwise the current directory
    initial_dir = os.path.abspath(config.OUTPUT_FOLDER) if os.path.exists(config.OUTPUT_FOLDER) else os.getcwd()

    folder = filedialog.askdirectory(
        title="Select Output Destination Folder",
        initialdir=initial_dir
    )
    if folder:
        selected_output_dir = folder
        output_folder_label.config(text=f"Output Folder: {os.path.basename(selected_output_dir)}")
        append_to_log(f"User selected output folder: {os.path.basename(selected_output_dir)}", tag="warning")
    else:
        selected_output_dir = ""
        output_folder_label.config(text="No output folder selected.")
        append_to_log("Output folder selection cancelled.")
    update_run_button_state()

# Enable/disable run button based on selections
def update_run_button_state():
    if selected_files_list and selected_output_dir:
        run_button.config(state=tk.NORMAL)
    else:
        run_button.config(state=tk.DISABLED)

# The function that runs the actual renaming process in a separate thread
def run_renamer_in_thread(files_to_process, output_folder):
    try:
        # Call the core processing logic with the selected files and folder
        process_receipts(files_to_process, output_folder, log_callback=append_to_log)
        
        # On successful completion, show a success message box
        root.after(0, lambda: messagebox.showinfo("Success", "Receipt renaming completed! Check log for details."))
    except Exception as e:
        root.after(0, lambda: messagebox.showerror("Error", f"An error occurred during processing:\n{str(e)}"))
        append_to_log(f"\nFATAL ERROR DURING PROCESSING: {str(e)}", tag="error")
    finally:
        # Always re-enable the select buttons and update run button state
        root.after(0, lambda: [
            select_files_button.config(state=tk.NORMAL),
            select_output_button.config(state=tk.NORMAL),
            update_run_button_state() # Will disable Run button if selections cleared
        ])

# Function called when the "Run" button is clicked
def start_renamer():
    # Clear previous log entries in the GUI display
    log_text.configure(state="normal")
    log_text.delete(1.0, tk.END)
    log_text.configure(state="disabled")

    # Double check if selections are made. This should be covered by button state but good for robustness.
    if not selected_files_list:
        append_to_log("Error: No files selected. Please select files to process.", tag="error")
        return
    if not selected_output_dir:
        append_to_log("Error: No output folder selected. Please choose a destination.", tag="error")
        return

    append_to_log("--- Receipt Renamer Configuration ---")
    append_to_log(f"Selected files to process: {len(selected_files_list)}")
    append_to_log(f"Selected output folder: {os.path.abspath(selected_output_dir)}")
    append_to_log(f"Logs will be saved to: {os.path.abspath(log_file_path)}")
    append_to_log("-" * 50)
    append_to_log("Starting receipt renaming process...")

    # Disable buttons during processing
    run_button.config(state=tk.DISABLED)
    select_files_button.config(state=tk.DISABLED)
    select_output_button.config(state=tk.DISABLED)

    # Start the renaming process in a new thread
    threading.Thread(target=run_renamer_in_thread, args=(selected_files_list, selected_output_dir), daemon=True).start()


# --- GUI Layout and Initialization ---

root = tk.Tk()
root.title("Receipt Renamer GUI")
root.geometry("600x650") # Adjust size
root.resizable(False, False)

main_frame = tk.Frame(root, padx=10, pady=10)
main_frame.pack(fill=tk.BOTH, expand=True)

title_label = tk.Label(main_frame, text="Receipt Renaming Automation", font=("Arial", 14, "bold"), pady=10)
title_label.pack()

# Instruction label for the user
instruction_text = (
    "1. Click 'Select Receipts' to choose the files you want to process.\n"
    "2. Click 'Select Destination' to choose where to save the renamed PDFs.\n"
    "3. Click 'Run Receipt Renamer'."
)
instruction_label = tk.Label(main_frame, text=instruction_text, padx=10, pady=10, justify=tk.LEFT)
instruction_label.pack()

# --- File Selection Section ---
select_files_button = tk.Button(main_frame, text="Select Receipts", command=select_receipt_files,
                                bg="#5cb85c", fg="white", font=("Arial", 10, "bold"), cursor="hand2")
select_files_button.pack(pady=(5, 2))
files_selected_label = tk.Label(main_frame, text="No files selected.", font=("Arial", 9, "italic"))
files_selected_label.pack(pady=(0, 10))

# --- Output Folder Selection Section ---
select_output_button = tk.Button(main_frame, text="Select Destination", command=select_output_destination,
                                 bg="#f0ad4e", fg="white", font=("Arial", 10, "bold"), cursor="hand2") # Orange button
select_output_button.pack(pady=(5, 2))
output_folder_label = tk.Label(main_frame, text="No output folder selected.", font=("Arial", 9, "italic"))
output_folder_label.pack(pady=(0, 10))


# --- Run Button ---
run_button = tk.Button(main_frame, text="Run Receipt Renamer", command=start_renamer,
                       bg="#0275d8", fg="white", # Blue button appearance
                       activebackground="#025aa5", activeforeground="white",
                       height=2, width=30, font=("Arial", 12, "bold"), cursor="hand2")
run_button.pack(pady=15)

# Initialize run button state (disabled until selections are made)
update_run_button_state()

# Separator/label for the log area
tk.Label(main_frame, text="--- Process Log ---", font=("Arial", 10, "italic")).pack(pady=5)

# ScrolledText widget for displaying real-time logs
log_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, state="disabled", font=("Courier New", 9),
                                      bg="#1e1e1e", fg="#FFFFFF", insertbackground="white", # Dark theme for log output, white text
                                      height=15)
log_text.pack(fill=tk.BOTH, expand=True)

root.mainloop()