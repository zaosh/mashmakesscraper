"""
Manages first-time setup and .env configuration.
"""
import os
import json
import config
from logger import log_info, log_error

SETUP_FILE = os.path.join(config.DATA_DIR, "setup_complete.json")
ENV_FILE = ".env"


def is_setup_complete():
    if not os.path.exists(SETUP_FILE):
        return False
    try:
        with open(SETUP_FILE, "r") as f:
            return json.load(f).get("setup_complete", False)
    except Exception:
        return False


def mark_setup_complete():
    with open(SETUP_FILE, "w") as f:
        json.dump({
            "setup_complete": True,
            "setup_date": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }, f, indent=4)
    log_info("Setup completed.")


def write_env_file(env_vars: dict):
    """Write or update the .env file."""
    existing = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    existing[key.strip()] = value.strip()

    existing.update(env_vars)

    sections = {
        "SLACK": ["SLACK_WEBHOOK_URL", "SLACK_ENABLED"],
        "GOOGLE SHEETS": ["GOOGLE_SPREADSHEET_ID", "GOOGLE_SERVICE_ACCOUNT_FILE"],
        "SYSTEM": ["HEADLESS_BROWSER", "RETRY_LIMIT", "ADMIN_PHONE"],
    }

    written_keys = set()
    lines = []

    for section_name, keys in sections.items():
        section_vars = {k: existing[k] for k in keys if k in existing}
        if section_vars:
            lines.append(f"# --- {section_name} ---")
            for k in keys:
                if k in existing:
                    lines.append(f"{k}={existing[k]}")
                    written_keys.add(k)
            lines.append("")

    remaining = {k: v for k, v in existing.items() if k not in written_keys}
    if remaining:
        lines.append("# --- OTHER ---")
        for k, v in remaining.items():
            lines.append(f"{k}={v}")
        lines.append("")

    with open(ENV_FILE, "w") as f:
        f.write("\n".join(lines))
    log_info(".env file updated.")


def save_service_account_file(file_bytes):
    """Save uploaded service account JSON to the project directory after validation."""
    import json as _json
    # Validate it's actually a Google service account JSON
    try:
        data = _json.loads(file_bytes)
        if not isinstance(data, dict):
            raise ValueError("Not a JSON object")
        required_fields = ["type", "project_id", "client_email", "private_key"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")
        if data.get("type") != "service_account":
            raise ValueError("Not a service account key file")
    except (_json.JSONDecodeError, ValueError) as e:
        log_error(f"Invalid service account file: {e}")
        raise ValueError(f"Invalid service account file: {e}")

    path = "service_account.json"
    with open(path, "wb") as f:
        f.write(file_bytes)
    log_info("Service account file saved.")
    return path


def test_slack_webhook(webhook_url):
    import requests
    import re
    if not webhook_url or not re.match(r'^https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[a-zA-Z0-9]+$', webhook_url):
        return False, "Invalid Slack webhook URL format"
    try:
        resp = requests.post(
            webhook_url,
            json={"text": "MashMakes Tracker: Slack connected!"},
            timeout=10,
        )
        if resp.status_code == 200 and resp.text == "ok":
            return True, "Connected"
        return False, f"Slack returned: {resp.status_code} {resp.text}"
    except Exception as e:
        return False, str(e)


def test_google_sheets(sheet_id, sa_file="service_account.json"):
    """Test Google Sheets connection and return the sheet title."""
    import re
    if not sheet_id or not re.match(r'^[a-zA-Z0-9_-]+$', sheet_id):
        return False, "Invalid Sheet ID format"
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds = Credentials.from_service_account_file(sa_file, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ])
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id)
        return True, f"Connected to '{sheet.title}'"
    except Exception as e:
        return False, str(e)


def test_dtdc_api():
    import requests
    try:
        resp = requests.post(
            "https://www.dtdc.com/wp-json/custom/v1/domestic/track",
            json={"trackType": "shipment", "trackNumber": "TEST"},
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200:
            return True, "DTDC API is reachable"
        return False, f"DTDC API returned {resp.status_code}"
    except Exception as e:
        return False, str(e)
