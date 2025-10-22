import os
from pathlib import Path
import dotenv

# Optional imports for platform-specific tools. Import only if available at runtime.
try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    import pdf2image
except Exception:
    pdf2image = None

# --- Load environment variables from a .env file if present ---
env_path = Path(__file__).with_name('.env')
if env_path.exists():
    dotenv.load_dotenv(dotenv_path=env_path)

# --- OpenAI API Configuration ---
# You can either set your OpenAI API key here directly (not recommended for VCS),
# or set the OPENAI_API_KEY environment variable, or put it in a .env file.
# To place the key directly in this file, set OPENAI_API_KEY_INLINE below to your key string.
# Example (do NOT commit real keys):
# OPENAI_API_KEY_INLINE = "sk-..."
OPENAI_API_KEY_INLINE = "my-api-key"

# Read from environment/ .env when inline key is not provided.
OPENAI_API_KEY = OPENAI_API_KEY_INLINE or os.getenv('OPENAI_API_KEY')

GPT_MODEL = os.getenv('GPT_MODEL', 'gpt-3.5-turbo')

# --- Folder Paths ---
INPUT_FOLDER = os.getenv('INPUT_FOLDER', 'input_receipts')
OUTPUT_FOLDER = os.getenv('OUTPUT_FOLDER', 'output_receipts')
LOG_FOLDER = os.getenv('LOG_FOLDER', 'logs')

# --- Tesseract and Poppler Paths ---
# Allow overriding via environment variables; only set the library paths if the libraries
# are importable and the provided path exists.
TESSERACT_CMD = os.getenv('TESSERACT_CMD')
if TESSERACT_CMD and pytesseract:
    if Path(TESSERACT_CMD).exists():
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

POPPLER_PATH = os.getenv('POPPLER_PATH')
if POPPLER_PATH and pdf2image:
    # pdf2image expects the path when calling convert_from_path; however some versions expose a global
    # setting. We set an attribute here only if available to avoid hard crashes. The build/run README
    # will explain how to supply poppler during conversion.
    try:
        # Newer pdf2image versions expose an environment variable use-case; this is defensive.
        pdf2image.converters.POPPLER_PATH = POPPLER_PATH
    except Exception:
        # Ignore if attribute not available; callers can pass the poppler_path parameter explicitly.
        pass
