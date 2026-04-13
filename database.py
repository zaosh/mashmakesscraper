import json
import os
import config
from logger import log_error, log_info, log_warning
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials


class DatabaseManager:
    """
    Google Sheets as the team's shared database.

    Sheet layout:
      "Active"    — AWBs currently being tracked (team adds rows here)
      "Delivered" — auto-moved here once status = Delivered

    Minimum columns the team needs to fill in the Active sheet:
      AWB Number | Customer Name | Phone Number

    The system auto-fills the rest:
      Last Status | Last Checked | Status Changes | SMS Sent | Failed Attempts
    """

    REQUIRED_HEADERS = [
        "AWB Number", "Customer Name", "Phone Number",
        "Last Status", "Last Checked", "Status Changes",
        "SMS Sent", "Failed Attempts",
    ]

    def __init__(self):
        self.state_file = config.STATE_FILE
        self.sheet = None
        self.active_ws = None
        self.delivered_ws = None
        self._connect()

    def _connect(self):
        sa_file = config.GOOGLE_SERVICE_ACCOUNT_FILE
        sheet_id = config.GOOGLE_SPREADSHEET_ID

        if not sheet_id:
            log_error("GOOGLE_SPREADSHEET_ID not set.")
            return
        if not os.path.exists(sa_file):
            log_error(f"Service account file not found: {sa_file}")
            return

        try:
            creds = Credentials.from_service_account_file(sa_file, scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ])
            client = gspread.authorize(creds)
            self.sheet = client.open_by_key(sheet_id)

            # Get or create Active worksheet
            self.active_ws = self._get_or_create_worksheet("Active")
            self._ensure_headers(self.active_ws)

            # Get or create Delivered worksheet
            self.delivered_ws = self._get_or_create_worksheet("Delivered")
            self._ensure_headers(self.delivered_ws)

            log_info("Connected to Google Sheets.")
        except Exception as e:
            log_error(f"Google Sheets connection failed: {str(e)}")

    def _get_or_create_worksheet(self, title):
        try:
            return self.sheet.worksheet(title)
        except gspread.exceptions.WorksheetNotFound:
            ws = self.sheet.add_worksheet(title=title, rows=100, cols=len(self.REQUIRED_HEADERS))
            log_info(f"Created '{title}' worksheet.")
            return ws

    def _ensure_headers(self, ws):
        """Make sure row 1 has the right headers."""
        existing = ws.row_values(1)
        if not existing:
            ws.append_row(self.REQUIRED_HEADERS, value_input_option="RAW")
            log_info(f"Added headers to '{ws.title}'.")
        else:
            # Add any missing columns
            for h in self.REQUIRED_HEADERS:
                if h not in existing:
                    col_idx = len(existing) + 1
                    ws.update_cell(1, col_idx, h)
                    existing.append(h)
                    log_info(f"Added missing column '{h}' to '{ws.title}'.")

    def is_connected(self):
        return self.active_ws is not None

    def get_orders(self):
        """Get all active (non-delivered) orders."""
        if not self.active_ws:
            return []
        try:
            records = self.active_ws.get_all_records()
            # Filter out empty rows (team might leave blank rows)
            return [r for r in records if str(r.get("AWB Number", "")).strip()]
        except Exception as e:
            log_error(f"Failed to read orders: {str(e)}")
            return []

    def update_order(self, awb_number, updates: dict):
        """Update fields for a specific AWB in the Active sheet."""
        if not self.active_ws:
            return False
        try:
            records = self.active_ws.get_all_records()
            headers = self.active_ws.row_values(1)

            for i, record in enumerate(records):
                if str(record.get("AWB Number", "")).strip() == str(awb_number).strip():
                    row_idx = i + 2  # +1 for header, +1 for 1-indexed
                    for key, value in updates.items():
                        if key in headers:
                            col_idx = headers.index(key) + 1
                            self.active_ws.update_cell(row_idx, col_idx, str(value))
                    return True

            log_warning(f"AWB {awb_number} not found in Active sheet.")
            return False
        except Exception as e:
            log_error(f"Failed to update AWB {awb_number}: {str(e)}")
            return False

    def move_to_delivered(self, awb_number):
        """Move a delivered order from Active to Delivered sheet, then delete from Active."""
        if not self.active_ws or not self.delivered_ws:
            return False
        try:
            records = self.active_ws.get_all_records()
            headers = self.active_ws.row_values(1)

            for i, record in enumerate(records):
                if str(record.get("AWB Number", "")).strip() == str(awb_number).strip():
                    row_idx = i + 2

                    # Build the row for Delivered sheet in header order
                    delivered_row = [str(record.get(h, "")) for h in self.REQUIRED_HEADERS]
                    self.delivered_ws.append_row(delivered_row, value_input_option="RAW")

                    # Delete from Active
                    self.active_ws.delete_rows(row_idx)

                    log_info(f"AWB {awb_number} moved to Delivered sheet.")
                    return True

            return False
        except Exception as e:
            log_error(f"Failed to move AWB {awb_number} to Delivered: {str(e)}")
            return False

    def get_delivered_count(self):
        """Count of delivered orders."""
        if not self.delivered_ws:
            return 0
        try:
            return max(0, len(self.delivered_ws.get_all_records()))
        except Exception:
            return 0

    # --- System state (local JSON, not in the sheet) ---

    def load_system_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "scraper_status": "Unknown",
            "last_run": "Never",
            "total_processed_today": 0,
            "success_today": 0,
            "failed_today": 0,
        }

    def update_system_state(self, updates: dict):
        state = self.load_system_state()
        state.update(updates)
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=4)
