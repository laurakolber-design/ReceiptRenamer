# receipt_renamer.py

import os
import re
import pytesseract
import openai
import pdf2image
from PIL import Image
from datetime import datetime
import csv
import json
import shutil

# Make sure config.py is in the same directory.
# Refer to previous instructions for config.py content and setup.
import config

# Setup OpenAI API key
openai.api_key = config.OPENAI_API_KEY # Corrected from openai.api_api_key

# This is only called if script is run directly, for GUI we pass folder dynamically
# os.makedirs(config.OUTPUT_FOLDER, exist_ok=True)
# os.makedirs(config.LOG_FOLDER, exist_ok=True)
# os.makedirs(os.path.join(config.OUTPUT_FOLDER, "failed_receipts"), exist_ok=True)
# os.makedirs(os.path.join(config.OUTPUT_FOLDER, "error_receipts"), exist_ok=True)


# Log file path (Still references config.LOG_FOLDER for consistency of logs)
log_file_path = os.path.join(config.LOG_FOLDER, "receipt_log.csv")

# Helper: Extract text from PDF or image
def extract_text(file_path, log_func=None):
    text = ""
    def _log(msg):
        # Use log_func if provided, otherwise print to console (for standalone execution)
        if log_func: log_func(msg)
        else: print(msg)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    if not os.access(file_path, os.R_OK):
        raise PermissionError(f"Cannot read file: {file_path}")

    if file_path.lower().endswith(".pdf"):
        _log(f"  - Extracting text from PDF: {os.path.basename(file_path)}")
        images = pdf2image.convert_from_path(file_path, dpi=300) # Increased DPI for better OCR
        for img in images:
            text += pytesseract.image_to_string(img)
    elif file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')): # Added common image formats
        _log(f"  - Extracting text from image: {os.path.basename(file_path)}")
        img = Image.open(file_path)
        text += pytesseract.image_to_string(img)
    else:
        raise ValueError(f"Unsupported file type: {os.path.basename(file_path)}. Only PDF and common image formats are supported.")
    return text

# Helper: Call GPT to parse the text
def parse_receipt_with_gpt(text, log_func=None):
    def _log(msg):
        if log_func: log_func(msg)
        else: print(msg)

    prompt = f"""
You are an expert receipt parsing assistant.
Your task is to precisely extract key information from the provided receipt text.

Extract the following fields:
- "RecipientOrgName": The full name of the organization that received the donation/payment. If not found, use "UNKNOWN".
- "Amount": The total donation or payment amount. Provide only the numerical value, without currency symbols ($) or commas. If multiple amounts are present, try to identify the final total. If not found, use "UNKNOWN".
- "Date": The date of the receipt or donation. Format this as MM.DD.YYYY (e.g., 01.15.2023). If not found, use "UNKNOWN".

Your response MUST be a valid JSON object CONTAINING ONLY the requested fields.
DO NOT include any conversational text, explanations, or additional characters outside the JSON.

Here is the receipt text to parse:
---
{text}
---

Example of expected JSON output:
{{
  "RecipientOrgName": "Some Charity Foundation",
  "Amount": "125.50",
  "Date": "03.22.2023"
}}
    """
    _log("  - Calling OpenAI GPT for parsing...")
    try:
        response = openai.chat.completions.create(
            model=config.GPT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0 # Use 0 for more deterministic output
        )

        content = response.choices[0].message.content.strip()

        parsed_json = json.loads(content)
        result = {
            "RecipientOrgName": parsed_json.get("RecipientOrgName", "UNKNOWN"),
            "Amount": parsed_json.get("Amount", "UNKNOWN"),
            "Date": parsed_json.get("Date", "UNKNOWN")
        }
    except openai.APIError as e:
        _log(f"  - OpenAI API error: {e}")
        result = {
            "RecipientOrgName": "UNKNOWN",
            "Amount": "UNKNOWN",
            "Date": "UNKNOWN"
        }
    except json.JSONDecodeError as e:
        _log(f"  - ERROR: GPT response was not valid JSON: {e}\nResponse content: '{content}'")
        result = {
            "RecipientOrgName": "UNKNOWN",
            "Amount": "UNKNOWN",
            "Date": "UNKNOWN"
        }
    except Exception as e:
        _log(f"  - An unexpected error occurred during GPT parsing: {e}")
        result = {
            "RecipientOrgName": "UNKNOWN",
            "Amount": "UNKNOWN",
            "Date": "UNKNOWN"
        }
    return result

# Main processing loop
# Now accepts a list of file paths and a user-selected output folder
def process_receipts(files_to_process: list, user_output_folder: str, log_callback=None):
    # Inner helper function to decide where to send log messages
    def log(message, tag=None):
        if log_callback:
            log_callback(message, tag)
        else:
            print(message) # Fallback to console print if no callback given

    if not files_to_process:
        log("No files selected for processing. Please select files first.", tag="warning")
        return # Exit early if no files

    if not user_output_folder:
        log("No output folder selected. Please choose a destination folder.", tag="warning")
        return # Exit early if no output folder

    # Ensure log folder exists (always from config to keep logs consistent)
    os.makedirs(config.LOG_FOLDER, exist_ok=True)

    # Create the user-selected output folder and its subfolders
    os.makedirs(user_output_folder, exist_ok=True)
    os.makedirs(os.path.join(user_output_folder, "failed_receipts"), exist_ok=True)
    os.makedirs(os.path.join(user_output_folder, "error_receipts"), exist_ok=True)

    log(f"Found {len(files_to_process)} files selected for processing.")
    log(f"Outputting processed files to: {os.path.abspath(user_output_folder)}")


    with open(log_file_path, mode='w', newline='', encoding='utf-8') as log_file:
        log_writer = csv.writer(log_file)
        log_writer.writerow(["Original Filename", "RecipientOrgName", "Amount", "Date", "New Filename", "Status", "Error Message"])

        for file_path in files_to_process: # Iterate directly over the provided file paths
            # Ensure filename is just the name, not full path, for logging and display
            filename = os.path.basename(file_path)
            log(f"\nProcessing '{filename}'...")

            recipient_for_log = "UNKNOWN"
            amount_for_log = "UNKNOWN"
            date_for_log = "UNKNOWN"
            final_output_filename = ""
            status = "FAILED"
            error_message = ""
            
            # target_output_folder will be determined dynamicall based on success/failure within the loop

            try:
                # 1. Extract Text
                text = extract_text(file_path, log_func=log)
                if not text.strip():
                    raise ValueError("No discernible text extracted from the file.")

                # 2. Parse with GPT
                parsed = parse_receipt_with_gpt(text, log_func=log)

                recipient_for_log = parsed["RecipientOrgName"]
                amount_for_log = parsed["Amount"]
                date_for_log = parsed["Date"]

                # --- FILENAME GENERATION LOGIC ---

                # Prepare recipient name for filename
                recipient_filename_part = recipient_for_log
                if recipient_filename_part == "UNKNOWN":
                    recipient_filename_part = "UnknownOrg"
                else:
                    # Remove characters not allowed or problematic in filenames, but keep spaces
                    recipient_filename_part = re.sub(r'[\\/:*?"<>|]', '', recipient_filename_part)
                    recipient_filename_part = re.sub(r'[\x00-\x1F]', '', recipient_filename_part)
                    recipient_filename_part = recipient_filename_part.strip()
                    # Convert CamelCase to spaced words if not already
                    recipient_filename_part = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", recipient_filename_part).strip()
                    # Replace multiple consecutive spaces with a single space
                    recipient_filename_part = re.sub(r"\s+", " ", recipient_filename_part)

                    # Limit length for very long names
                    if len(recipient_filename_part) > 50:
                        recipient_filename_part = recipient_filename_part[:50].strip()


                # Prepare amount for filename (just the number)
                amount_filename_part = amount_for_log
                if amount_filename_part == "UNKNOWN":
                    amount_filename_part = "UnknownAmount"
                else:
                    # Keep only digits and a single decimal point, then take integer part
                    amount_filename_part = re.sub(r"[^\d.]", "", amount_filename_part)
                    if '.' in amount_filename_part:
                        amount_filename_part = amount_filename_part.split('.')[0]
                    if not amount_filename_part:
                        amount_filename_part = "0"

                # Prepare date for filename (use GPT's MM.DD.YYYY directly)
                date_filename_part = date_for_log
                if date_filename_part == "UNKNOWN":
                    date_filename_part = "UnknownDate"

                # Determine the final filename and target folder based on success/failure
                if "UNKNOWN" in [recipient_for_log, amount_for_log, date_for_log]:
                    status = "FAILED - Missing Data"
                    base_new_filename = f"FAILED_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.path.splitext(filename)[0]}"
                    target_output_folder = os.path.join(user_output_folder, "failed_receipts")
                    log(f"  - Status: {status}. Moving to '{target_output_folder}'.")
                else:
                    status = "SUCCESS"
                    # Construct the filename with spaces for recipient, _$ prefix for amount, and original date format
                    base_new_filename = f"{recipient_filename_part}_${amount_filename_part}_{date_filename_part}"
                    target_output_folder = user_output_folder # Processed files go to the main user-selected folder
                    log(f"  - Status: {status}. Moving to '{target_output_folder}'.")

                # Ensure uniqueness of the output filename
                new_filename_attempt = f"{base_new_filename}.pdf"
                counter = 1
                final_output_path = os.path.join(target_output_folder, new_filename_attempt)
                while os.path.exists(final_output_path):
                    new_filename_attempt = f"{base_new_filename}_{counter}.pdf"
                    final_output_path = os.path.join(target_output_folder, new_filename_attempt)
                    counter += 1

                final_output_filename = os.path.basename(final_output_path)

                # --- END OF FILENAME GENERATION LOGIC ---

                # 3. Perform File Operations (Move/Convert)
                # IMPORTANT: We are copying the file from its original location to the new output location.
                # The original file is NOT deleted from its original location.
                # If you wish to MOVE and delete the original, use shutil.move instead of shutil.copy2
                # and os.remove for image files. For now, we will prefer safety (copy).
                if file_path.lower().endswith(".pdf"):
                    shutil.copy2(file_path, final_output_path) # Retains file metadata
                    log(f"  - Copied '{filename}' to '{final_output_filename}'.")
                else: # It's an image file
                    img = Image.open(file_path)
                    img.save(final_output_path, "PDF")
                    log(f"  - Converted '{filename}' to PDF and saved as '{final_output_filename}'. (Original image not moved or deleted)")

            except Exception as e:
                error_message = str(e)
                status = f"ERROR - {error_message}"
                log(f"  - ERROR processing '{filename}': {error_message}", tag="error")

                error_output_folder = os.path.join(user_output_folder, "error_receipts") # Error files go to the error subfolder
                error_new_filename_base = f"ERROR_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.path.splitext(filename)[0]}"
                error_new_filename_attempt = f"{error_new_filename_base}.pdf"
                error_counter = 1
                error_final_output_path = os.path.join(error_output_folder, error_new_filename_attempt)
                while os.path.exists(error_final_output_path):
                    error_new_filename_attempt = f"{error_new_filename_base}_{error_counter}.pdf"
                    error_final_output_path = os.path.join(error_output_folder, error_new_filename_attempt)
                    error_counter += 1

                final_output_filename = os.path.basename(error_final_output_path)

                try:
                    # Attempt to copy the problematic file to the error folder for review
                    if os.path.exists(file_path):
                        if file_path.lower().endswith(".pdf"):
                            shutil.copy2(file_path, error_final_output_path)
                        else:
                            img = Image.open(file_path)
                            img.save(error_final_output_path, "PDF")
                        log(f"  - Copied '{filename}' to error folder as '{final_output_filename}'.")
                    else:
                        log(f"  - Original file '{filename}' was missing or already processed. Cannot copy to error folder.")
                except Exception as copy_error: # Changed from move_error to copy_error
                    log(f"  - CRITICAL ERROR: Could not copy '{filename}' to error folder '{error_output_folder}': {copy_error}", tag="error")
                    status = f"CRITICAL ERROR - {copy_error}"
                    error_message = f"Failed to copy to error folder: {copy_error}"

            finally:
                log_writer.writerow([
                    filename,
                    recipient_for_log,
                    amount_for_log,
                    date_for_log,
                    final_output_filename,
                    status,
                    error_message
                ])
                log_file.flush()

    log("\nReceipt processing complete.")
    log(f"Check '{log_file_path}' for details and '{os.path.abspath(user_output_folder)}' for processed files (and subfolders for failed/error).")

# This block is for when receipt_renamer.py is run directly (not via GUI).
# It serves as a fallback or for command-line testing.
if __name__ == "__main__":
    # If run directly, default to config folders for input/output
    default_input_folder = config.INPUT_FOLDER
    default_output_folder = config.OUTPUT_FOLDER

    os.makedirs(default_input_folder, exist_ok=True) # Ensure default input folder exists
    print(f"Input receipts should be placed in: {os.path.abspath(default_input_folder)}")
    print(f"Processed receipts will be saved to: {os.path.abspath(default_output_folder)}")
    print(f"Logs will be saved to: {os.path.abspath(config.LOG_FOLDER)}")
    print("-" * 50)

    # Get files from the default input folder if run standalone
    files_in_input = {os.path.join(default_input_folder, f) for f in os.listdir(default_input_folder) if os.path.isfile(os.path.join(default_input_folder, f))}
    process_receipts(list(files_in_input), default_output_folder)