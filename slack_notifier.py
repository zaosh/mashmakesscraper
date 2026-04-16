import requests
import config
from logger import log_info, log_error, log_warning


def _send_slack_message(blocks, text_fallback):
    """
    Sends a message to the configured Slack webhook.
    Returns True on success, False on failure.
    """
    if not config.SLACK_ENABLED:
        return False

    if not config.SLACK_WEBHOOK_URL or "hooks.slack.com" not in config.SLACK_WEBHOOK_URL:
        log_warning("Slack webhook URL not configured. Skipping notification.")
        return False

    payload = {"text": text_fallback, "blocks": blocks}

    try:
        resp = requests.post(config.SLACK_WEBHOOK_URL, json=payload, timeout=10)
        if resp.status_code == 200 and resp.text == "ok":
            log_info("Slack notification sent successfully.")
            return True
        else:
            log_error(f"Slack webhook returned {resp.status_code}: {resp.text}")
            return False
    except requests.exceptions.Timeout:
        log_error("Slack webhook request timed out.")
        return False
    except Exception as e:
        log_error(f"Slack notification failed: {str(e)}")
        return False


def _load_custom_messages():
    """Load custom message templates from system state."""
    import json
    import os
    try:
        state_file = os.path.join(config.DATA_DIR, "system_state.json")
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                state = json.load(f)
            return {
                "delivered": state.get("custom_msg_delivered", ""),
                "status_change": state.get("custom_msg_status_change", ""),
            }
    except Exception:
        pass
    return {"delivered": "", "status_change": ""}


def _format_custom_message(template, order_id, customer_name, awb, old_status, new_status):
    """Replace placeholders in a custom message template."""
    if not template:
        return ""
    return (template
            .replace("{order_id}", str(order_id))
            .replace("{customer}", str(customer_name))
            .replace("{awb}", str(awb))
            .replace("{old_status}", str(old_status))
            .replace("{new_status}", str(new_status)))


def notify_status_change(order_id, customer_name, awb, old_status, new_status):
    is_delivered = "delivered" in new_status.lower()
    custom_msgs = _load_custom_messages()

    # Pick the right custom message template
    if is_delivered and custom_msgs["delivered"]:
        custom_text = _format_custom_message(
            custom_msgs["delivered"], order_id, customer_name, awb, old_status, new_status)
    elif custom_msgs["status_change"]:
        custom_text = _format_custom_message(
            custom_msgs["status_change"], order_id, customer_name, awb, old_status, new_status)
    else:
        custom_text = ""

    header = "Order Delivered!" if is_delivered else "Shipment Status Update"
    text = f"Shipment {order_id} ({awb}) status changed: {old_status} -> {new_status}"
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Order ID:*\n{order_id}"},
                {"type": "mrkdwn", "text": f"*Customer:*\n{customer_name}"},
                {"type": "mrkdwn", "text": f"*AWB:*\n{awb}"},
                {"type": "mrkdwn", "text": f"*New Status:*\n{new_status}"},
            ]
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Previous status: _{old_status}_"}
            ]
        }
    ]
    if custom_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": custom_text}
        })
    return _send_slack_message(blocks, text)


def notify_scrape_failure(order_id, awb, reason, failed_attempts, retry_limit):
    severity = "CRITICAL" if failed_attempts >= retry_limit else "Warning"
    emoji = ":red_circle:" if failed_attempts >= retry_limit else ":warning:"
    text = f"{severity}: Scraping failed for order {order_id} (AWB {awb}) - attempt {failed_attempts}/{retry_limit}"
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{severity}: Scrape Failed"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Order ID:*\n{order_id}"},
                {"type": "mrkdwn", "text": f"*AWB:*\n{awb}"},
                {"type": "mrkdwn", "text": f"*Attempts:*\n{failed_attempts}/{retry_limit}"},
                {"type": "mrkdwn", "text": f"*Severity:*\n{emoji} {severity}"},
            ]
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Reason:*\n```{reason}```"}
        },
    ]
    if failed_attempts >= retry_limit:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": ":no_entry: *This order has been marked as Failed.* Use the dashboard to retry manually."}
        })
    return _send_slack_message(blocks, text)


def notify_batch_complete(total, success_count, fail_count, scraper_status):
    if total == 0:
        return False

    if scraper_status == "Working":
        emoji = ":white_check_mark:"
        color_text = "All orders tracked successfully."
    elif scraper_status == "Warning":
        emoji = ":warning:"
        color_text = "Some orders failed to track. Check the dashboard for details."
    else:
        emoji = ":rotating_light:"
        color_text = "*CRITICAL: All orders failed to track.* The scraper may be broken."

    text = f"Batch complete: {success_count}/{total} succeeded, {fail_count} failed ({scraper_status})"
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Tracking Batch Complete"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Total Processed:*\n{total}"},
                {"type": "mrkdwn", "text": f"*Successful:*\n{success_count}"},
                {"type": "mrkdwn", "text": f"*Failed:*\n{fail_count}"},
                {"type": "mrkdwn", "text": f"*Status:*\n{emoji} {scraper_status}"},
            ]
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": color_text}]
        }
    ]
    return _send_slack_message(blocks, text)


def notify_scraper_collapse(error_message):
    text = f"CRITICAL: MashMakes scraper has collapsed - {error_message}"
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":fire: SCRAPER COLLAPSE DETECTED"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*The tracking system failed on ALL orders.*\n\n"
                    "Likely causes:\n"
                    "- DTDC changed their website or API\n"
                    "- The tracking site is down or blocking requests\n"
                    "- Network issues on the server\n\n"
                    "*Immediate action required:*\n"
                    "1. Check the dashboard logs for error details\n"
                    "2. Run `python test_system.py` with a known AWB to verify\n"
                    "3. Inspect `failure.html` for the last page the scraper saw\n"
                    "4. Update selectors in `scraper.py` if the site layout changed"
                )
            }
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Error:*\n```{error_message}```"}
        },
    ]
    return _send_slack_message(blocks, text)


def notify_daily_summary(total_orders, total_failed, total_sms, success_today, failed_today):
    health = ":white_check_mark: Healthy" if failed_today == 0 else ":warning: Issues detected"
    text = f"Daily Summary: {total_orders} orders, {total_failed} failed, {total_sms} SMS sent"
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Daily Summary Report"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Total Orders:*\n{total_orders}"},
                {"type": "mrkdwn", "text": f"*Orders Failed:*\n{total_failed}"},
                {"type": "mrkdwn", "text": f"*SMS Notifications Sent:*\n{total_sms}"},
                {"type": "mrkdwn", "text": f"*System Health:*\n{health}"},
            ]
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Tracked Successfully Today:*\n{success_today}"},
                {"type": "mrkdwn", "text": f"*Failed Today:*\n{failed_today}"},
            ]
        },
    ]
    return _send_slack_message(blocks, text)


def test_slack_connection():
    text = "MashMakes Tracker: Slack connection test successful!"
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": ":white_check_mark: *MashMakes Tracker* connected to Slack successfully."}
        }
    ]
    return _send_slack_message(blocks, text)
