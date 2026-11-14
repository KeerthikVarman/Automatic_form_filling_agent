import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from root directory if available
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_FALLBACK_MODELS = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

# Default starting URL (can be overridden by user in UI or per session)
STARTING_URL = os.getenv("STARTING_URL", "https://httpbin.org/forms/post")
# Allow all web domains universally
APPROVED_DOMAINS = ["*"]

BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "5173"))
