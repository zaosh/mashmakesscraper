import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Admin & Alerts
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "")

# SMS Provider configuration
ACTIVE_SMS_PROVIDER = os.getenv("ACTIVE_SMS_PROVIDER", "FAST2SMS").upper()
FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")

# Scraping settings
HEADLESS_BROWSER = os.getenv("HEADLESS_BROWSER", "True").lower() in ('true', '1', 't')
RETRY_LIMIT = int(os.getenv("RETRY_LIMIT", 3))

# Local Files Backup (State / Logs)
DATA_DIR = "data"
LOG_FILE = os.path.join(DATA_DIR, "system.log")
STATE_FILE = os.path.join(DATA_DIR, "system_state.json")

os.makedirs(DATA_DIR, exist_ok=True)

# Slack Integration
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SLACK_ENABLED = os.getenv("SLACK_ENABLED", "True").lower() in ('true', '1', 't')

# Google Sheets Database
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
GOOGLE_SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "")

