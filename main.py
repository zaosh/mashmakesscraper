import time
import schedule
from datetime import datetime
import config
from logger import log_info, log_error, log_warning
from database import DatabaseManager
from scraper import get_status_with_retry
from sms import send_customer_update, alert_admin
from slack_notifier import (
    notify_status_change, notify_scrape_failure,
    notify_batch_complete, notify_scraper_collapse, notify_daily_summary,
)

# Lazy-init: created on first use, not at import time.
# This avoids a stale connection when dashboard imports process_single_order.
_db = None


def _get_db():
    global _db
    if _db is None:
        _db = DatabaseManager()
    return _db


def process_single_order(row, db=None):
    if db is None:
        db = _get_db()

    awb = str(row.get("AWB Number", "")).strip()
    customer_name = str(row.get("Customer Name", "")).strip()
    phone = str(row.get("Phone Number", "")).strip()
    last_status = str(row.get("Last Status", "")).strip()
    failed_attempts = int(row.get("Failed Attempts", 0) or 0)

    if not awb:
        return False, "No AWB"

    log_info(f"Processing AWB: {awb} ({customer_name})")

    success, current_status = get_status_with_retry(awb)

    if not success:
        log_error(f"Failed to track AWB {awb}: {current_status}")

        failed_attempts += 1
        db.update_order(awb, {
            "Failed Attempts": failed_attempts,
            "Last Checked": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

        notify_scrape_failure(awb, awb, current_status, failed_attempts, config.RETRY_LIMIT)
        return False, "Scrape Failed"

    # Check if status changed
    if current_status != last_status:
        log_info(f"Status changed for {awb}: '{last_status}' -> '{current_status}'")

        # Notify Slack
        notify_status_change(awb, customer_name, awb, last_status, current_status)

        # Send SMS if phone is available
        sms_sent = False
        if phone:
            sms_sent = send_customer_update(awb, customer_name, phone, current_status, awb)

        status_changes = int(row.get("Status Changes", 0) or 0) + 1
        db.update_order(awb, {
            "Last Status": current_status,
            "Status Changes": status_changes,
            "Last Checked": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "SMS Sent": "Yes" if sms_sent else "No",
            "Failed Attempts": 0,
        })

        # Auto-clear: move delivered orders to the Delivered sheet
        if "delivered" in current_status.lower():
            log_info(f"AWB {awb} delivered — moving to Delivered sheet.")
            db.move_to_delivered(awb)

        return True, "Updated"
    else:
        log_info(f"No change for AWB {awb}.")
        db.update_order(awb, {
            "Last Checked": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Failed Attempts": 0,
        })
        return True, "No Change"


def run_tracking_batch():
    db = _get_db()
    log_info("--- Starting Tracking Batch ---")

    # Refresh connection if token is stale
    db._ensure_fresh_connection()

    if not db.is_connected():
        log_info("DB not connected, retrying...")
        db._connect()

    if not db.is_connected():
        log_error("Not connected to Google Sheets. Skipping batch.")
        db.update_system_state({
            "last_run": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "scraper_status": "Error (No DB)",
        })
        return

    orders = db.get_orders()

    if not orders:
        log_info("No active orders to track.")
        db.update_system_state({
            "last_run": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "scraper_status": "Idle (No Orders)",
        })
        return

    success_count = 0
    fail_count = 0
    total = len(orders)

    for row in orders:
        try:
            success, reason = process_single_order(row, db=db)
            if success:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            log_error(f"Error processing AWB {row.get('AWB Number', '?')}: {str(e)}")
            fail_count += 1

        # Small delay between requests to be respectful
        time.sleep(2)

    log_info(f"--- Batch Complete --- Total: {total}, Success: {success_count}, Failed: {fail_count}")

    status = "Working" if fail_count == 0 else ("Warning" if success_count > 0 else "Failing")

    db.update_system_state({
        "last_run": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "scraper_status": status,
        "total_processed_today": total,
        "success_today": success_count,
        "failed_today": fail_count,
    })

    notify_batch_complete(total, success_count, fail_count, status)

    # Critical: 100% failure on 2+ orders = scraper is broken
    if fail_count == total and total > 1:
        error_msg = "All orders failed to track. DTDC API or site may have changed."
        log_error(error_msg)
        alert_admin(error_msg)
        notify_scraper_collapse(error_msg)


def send_daily_summary():
    db = _get_db()
    log_info("Generating daily summary...")
    db._ensure_fresh_connection()
    state = db.load_system_state()
    orders = db.get_orders()
    delivered_count = db.get_delivered_count()

    active_count = len(orders)
    success_today = state.get("success_today", 0)
    failed_today = state.get("failed_today", 0)

    summary = (
        f"Daily Summary:\n"
        f"Active Orders: {active_count}\n"
        f"Delivered (total): {delivered_count}\n"
        f"Tracked Today: {success_today}\n"
        f"Failed Today: {failed_today}"
    )

    alert_admin(summary)
    notify_daily_summary(active_count, failed_today, 0, success_today, failed_today)
    log_info("Daily summary sent.")

    db.update_system_state({
        "success_today": 0,
        "failed_today": 0,
        "total_processed_today": 0,
    })


def check_new_orders():
    """Quick check for newly added AWBs (no Last Status yet) and track them immediately."""
    db = _get_db()
    db._ensure_fresh_connection()
    if not db.is_connected():
        return

    orders = db.get_orders()
    new_orders = [r for r in orders if not str(r.get("Last Status", "")).strip()]

    if not new_orders:
        return

    log_info(f"Found {len(new_orders)} new AWB(s) — tracking now.")

    for row in new_orders:
        try:
            process_single_order(row, db=db)
        except Exception as e:
            log_error(f"Error processing new AWB {row.get('AWB Number', '?')}: {str(e)}")
        time.sleep(2)


def start_scheduler():
    log_info("Scheduler started.")

    # Run once at startup
    run_tracking_batch()

    # Every 3 hours — full batch
    schedule.every(3).hours.do(run_tracking_batch)

    # Every 5 minutes — check for newly added AWBs only
    schedule.every(5).minutes.do(check_new_orders)

    # Daily summary at 18:00
    schedule.every().day.at("18:00").do(send_daily_summary)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    start_scheduler()
