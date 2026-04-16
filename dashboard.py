import streamlit as st
import os
import time
import config
from database import DatabaseManager
from logger import get_recent_logs
from setup_manager import (
    is_setup_complete, mark_setup_complete, write_env_file,
    save_service_account_file, test_slack_webhook,
    test_google_sheets, test_dtdc_api,
)

st.set_page_config(page_title="MashMakes Tracker", page_icon="📦", layout="wide")


def _reload_config():
    """Reload .env into config module so changes take effect without restart."""
    from dotenv import load_dotenv
    load_dotenv(override=True)
    config.GOOGLE_SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "")
    config.GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    config.SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
    config.SLACK_ENABLED = os.getenv("SLACK_ENABLED", "True").lower() in ('true', '1', 't')


# ============================================================
# GOOGLE AUTH LOGIN
# ============================================================
def google_auth_gate():
    allowed_emails = os.getenv("ALLOWED_EMAILS", "")
    allowed_domain = os.getenv("ALLOWED_DOMAIN", "")

    if not allowed_emails and not allowed_domain:
        return True

    user_email = st.experimental_user.get("email", "") if hasattr(st, "experimental_user") else ""

    if not user_email:
        st.title("Access Restricted")
        st.error(
            "This dashboard requires Google authentication.\n\n"
            "Please access this through your company's SSO portal, "
            "or ask your admin to add your email to ALLOWED_EMAILS in .env"
        )
        st.stop()
        return False

    if allowed_domain and not user_email.endswith(f"@{allowed_domain}"):
        st.title("Access Denied")
        st.error(f"Your email ({user_email}) is not from the allowed domain (@{allowed_domain}).")
        st.stop()
        return False

    if allowed_emails:
        email_list = [e.strip().lower() for e in allowed_emails.split(",")]
        if user_email.lower() not in email_list:
            st.title("Access Denied")
            st.error(f"Your email ({user_email}) is not in the allowed list.")
            st.stop()
            return False

    return True


# ============================================================
# FIRST-TIME SETUP WIZARD
# ============================================================
def run_setup_wizard():
    st.title("MashMakes Tracker — Setup")
    st.markdown("Let's get your shipment tracking system running. This takes about 5 minutes.")
    st.markdown("---")

    if "setup_step" not in st.session_state:
        st.session_state["setup_step"] = 1

    step = st.session_state["setup_step"]
    st.progress(step / 3)

    # ---- STEP 1: Google Sheets ----
    if step == 1:
        st.header("Step 1 of 3 — Connect Google Sheets")

        st.markdown("""
**This is your team's shared database.** Anyone with access to the Google Sheet can add
AWB numbers from any device (phone, laptop, tablet). The system watches the sheet,
tracks each shipment, sends updates to Slack, and auto-clears delivered orders.
""")

        st.subheader("A. Create your Google Sheet")
        st.markdown("""
1. Open [Google Sheets](https://sheets.google.com) and create a **new blank spreadsheet**
2. Name it something like **"MashMakes Shipments"**
3. **Copy the Sheet ID from the URL bar** — it's the long random string:

   `https://docs.google.com/spreadsheets/d/`**`THIS_PART_IS_THE_ID`**`/edit`
""")

        sheet_id = st.text_input(
            "Paste your Google Sheet ID here",
            placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
            key="w_sheet_id",
        )

        st.markdown("---")

        st.subheader("B. Create a Service Account (one-time, ~3 minutes)")
        st.markdown("""
A "service account" is like a robot Google account that lets this system read and write
to your Sheet. You create it once and never have to touch it again.
""")

        with st.expander("Step-by-step instructions (click to expand)", expanded=True):
            st.markdown("""
**1. Go to Google Cloud Console**
- Open [console.cloud.google.com](https://console.cloud.google.com)
- Sign in with your company Google account
- If it asks you to create a project, click **"Create Project"**, name it anything
  (e.g., "MashMakes Tracker"), and click **Create**

**2. Enable the Google Sheets API**
- In the search bar at the top, type **"Google Sheets API"**
- Click on it, then click the blue **"Enable"** button

**3. Create the Service Account**
- In the search bar, type **"Service Accounts"** and click the result under IAM
- Click **"+ Create Service Account"** at the top
- Name: `mashmakes-tracker` (or anything you like)
- Click **Create and Continue** -> select **Editor** role -> click **Done**

**4. Download the Key File**
- Click on your new service account in the list
- Go to the **"Keys"** tab
- Click **"Add Key" -> "Create new key"** -> choose **JSON** -> click **Create**
- A `.json` file will download — **upload it below**

**5. Share your Google Sheet with the service account**
- Open the downloaded JSON file in Notepad
- Find `"client_email": "something@something.iam.gserviceaccount.com"`
- Copy that email address
- Go to your Google Sheet -> click **Share** -> paste the email -> **Editor** access
""")

        st.warning("**Keep the JSON file safe.** It's like a password for your Google Sheet.")

        sa_upload = st.file_uploader(
            "Upload the JSON key file you downloaded in step 4",
            type=["json"],
            key="w_sa_file",
        )

        if sa_upload:
            try:
                import json as _json
                sa_data = _json.loads(sa_upload.getvalue())
                sa_email = sa_data.get("client_email", "")
                if sa_email:
                    st.success(f"File looks good! Service account email: `{sa_email}`")
                    st.info(
                        f"**Important:** Make sure you shared your Google Sheet with "
                        f"`{sa_email}` as an **Editor**."
                    )
                else:
                    st.error("This file is missing a `client_email` field. "
                             "Make sure you downloaded the JSON key from Service Accounts.")
            except Exception:
                st.error("Couldn't read this file. Make sure it's the .json key file from Google.")

        st.markdown("---")

        col_test, col_next = st.columns(2)
        with col_test:
            if st.button("Test Connection", key="test_sheets"):
                if sa_upload and sheet_id:
                    with st.spinner("Testing Google Sheets connection..."):
                        sa_path = save_service_account_file(sa_upload.getvalue())
                        ok, msg = test_google_sheets(sheet_id, sa_path)
                        if ok:
                            st.success(f"{msg}")
                        else:
                            st.error(f"Failed: {msg}")
                            if "403" in str(msg):
                                st.warning("**Permission denied.** Share the Google Sheet with the service account email as Editor.")
                            elif "not found" in str(msg).lower():
                                st.warning("**Sheet not found.** Double-check the Sheet ID (the long string from the URL).")
                else:
                    st.warning("Upload the JSON file and enter the Sheet ID first.")

        with col_next:
            if st.button("Next ->", key="step1_next"):
                if not sa_upload or not sheet_id:
                    st.error("Both the service account file and Sheet ID are required.")
                else:
                    save_service_account_file(sa_upload.getvalue())
                    st.session_state["cfg_sheet_id"] = sheet_id
                    st.session_state["setup_step"] = 2
                    st.rerun()

    # ---- STEP 2: Slack ----
    elif step == 2:
        st.header("Step 2 of 3 — Connect Slack")

        st.markdown("""
**This is how your team gets notified.** Every time a shipment status changes, the system
posts a message to your Slack channel. You'll also get:
- Status change alerts (e.g., "In Transit" -> "Out for Delivery")
- Error alerts if tracking fails
- A daily summary at 6 PM
- Immediate warning if the tracking system breaks
""")

        with st.expander("Step-by-step: How to get a Slack Webhook URL (click to expand)", expanded=True):
            st.markdown("""
**1. Open Slack API**
- Go to [api.slack.com/apps](https://api.slack.com/apps) in your browser
- Sign in with the same Slack account your team uses

**2. Create a New App**
- Click **"Create New App"** -> **"From scratch"**
- App Name: `MashMakes Tracker` (or anything you like)
- Pick your **workspace** -> click **"Create App"**

**3. Enable Webhooks**
- On the left sidebar, click **"Incoming Webhooks"**
- Toggle the switch to **ON**
- Scroll down and click **"Add New Webhook to Workspace"**
- Pick the **channel** (e.g., `#shipments`) -> click **"Allow"**

**4. Copy the URL**
- You'll see a URL like: `https://hooks.slack.com/services/TXXXXX/BXXXXX/XXXXXXXXXX`
- Click **"Copy"** and paste it below
""")

        st.warning("**Keep this URL private.** Anyone with it can post to your Slack channel.")

        webhook_url = st.text_input(
            "Paste your Slack Webhook URL here",
            placeholder="https://hooks.slack.com/services/T.../B.../xxx",
            key="w_slack_url",
        )

        if webhook_url:
            if st.button("Test Slack Connection", key="test_slack"):
                with st.spinner("Sending test message to Slack..."):
                    ok, msg = test_slack_webhook(webhook_url)
                    if ok:
                        st.success("Slack connected! Check your channel for the test message.")
                    else:
                        st.error(f"Failed: {msg}")
                        if "invalid" in str(msg).lower():
                            st.warning("Make sure you copied the full URL starting with `https://hooks.slack.com/services/`")

        col_back, col_next = st.columns(2)
        with col_back:
            if st.button("<- Back", key="step2_back"):
                st.session_state["setup_step"] = 1
                st.rerun()
        with col_next:
            if st.button("Next ->", key="step2_next"):
                if not webhook_url:
                    st.error("Slack webhook URL is required.")
                elif "hooks.slack.com" not in webhook_url:
                    st.error("That doesn't look like a valid Slack webhook URL.")
                else:
                    st.session_state["cfg_slack_url"] = webhook_url
                    st.session_state["setup_step"] = 3
                    st.rerun()

    # ---- STEP 3: System Check & Finish ----
    elif step == 3:
        st.header("Step 3 of 3 — System Check")
        st.markdown("Verifying all connections before we go live.")

        # DTDC API
        with st.spinner("Testing DTDC tracking API..."):
            dtdc_ok, dtdc_msg = test_dtdc_api()
        if dtdc_ok:
            st.success(f"DTDC API: {dtdc_msg}")
        else:
            st.error(f"DTDC API: {dtdc_msg}")
            st.warning("DTDC API not reachable. The system will fall back to browser scraping.")

        # Google Sheets
        sheet_id = st.session_state.get("cfg_sheet_id", "")
        with st.spinner("Testing Google Sheets..."):
            gs_ok, gs_msg = test_google_sheets(sheet_id)
        if gs_ok:
            st.success(f"Google Sheets: {gs_msg}")
        else:
            st.error(f"Google Sheets: {gs_msg}")

        # Slack
        slack_url = st.session_state.get("cfg_slack_url", "")
        if slack_url and "hooks.slack.com" in slack_url:
            st.success("Slack: Configured")
        else:
            st.warning("Slack: Not configured")

        st.markdown("---")
        st.subheader("How the system works")
        st.markdown("""
1. **Your team adds AWB numbers** to the Google Sheet's "Active" tab (from any device)
2. **Every 3 hours**, the system checks each AWB against DTDC
3. **When a status changes**, it updates the sheet and sends a Slack notification
4. **When an order is delivered**, it auto-moves to the "Delivered" tab
5. **At 6 PM daily**, it sends a summary to Slack
6. **If things break**, it alerts Slack immediately
""")

        col_back, col_finish = st.columns(2)
        with col_back:
            if st.button("<- Back", key="step3_back"):
                st.session_state["setup_step"] = 2
                st.rerun()
        with col_finish:
            if st.button("Complete Setup", type="primary", key="finish_setup"):
                env_vars = {
                    "GOOGLE_SPREADSHEET_ID": sheet_id,
                    "GOOGLE_SERVICE_ACCOUNT_FILE": "service_account.json",
                    "SLACK_WEBHOOK_URL": st.session_state.get("cfg_slack_url", ""),
                    "SLACK_ENABLED": "True",
                    "HEADLESS_BROWSER": "True",
                    "RETRY_LIMIT": "3",
                }
                write_env_file(env_vars)
                mark_setup_complete()
                _reload_config()

                # Initialize DB (creates Active/Delivered sheets)
                DatabaseManager()

                st.success("Setup complete! Your tracking system is ready.")
                st.balloons()
                time.sleep(2)
                st.rerun()


# ============================================================
# MAIN DASHBOARD
# ============================================================
def run_dashboard():
    st.title("MashMakes Shipment Tracker")
    _reload_config()

    db = DatabaseManager()

    # --- SYSTEM HEALTH ---
    state = db.load_system_state()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Live DTDC API status instead of stale scraper state
        last_run = state.get("last_run", "Never")
        scraper_status = state.get("scraper_status", "Not Run")
        if scraper_status == "Working":
            st.success(f"Tracker: {scraper_status}")
        elif scraper_status in ("Warning", "Idle (No Orders)"):
            st.warning(f"Tracker: {scraper_status}")
        elif last_run == "Never" or scraper_status in ("Not Run", "Unknown"):
            st.info("Tracker: Awaiting first run")
        else:
            st.error(f"Tracker: {scraper_status}")

    with col2:
        if config.SLACK_ENABLED and config.SLACK_WEBHOOK_URL and "hooks.slack.com" in config.SLACK_WEBHOOK_URL:
            st.success("Slack: Connected")
        else:
            st.warning("Slack: Not configured")

    with col3:
        st.info(f"Last Run: {state.get('last_run', 'Never')}")

    with col4:
        st.metric("Today", f"{state.get('success_today', 0)} ok / {state.get('failed_today', 0)} failed")

    st.markdown("---")

    # --- CONNECTION CHECK ---
    if not db.is_connected():
        st.error("Not connected to Google Sheets. Check your service account file and Sheet ID.")
        st.stop()

    # --- ACTIVE ORDERS ---
    orders = db.get_orders()
    delivered_count = db.get_delivered_count()

    tab_active, tab_delivered = st.tabs([
        f"Active Orders ({len(orders)})",
        f"Delivered ({delivered_count})",
    ])

    with tab_active:
        if not orders:
            st.info(
                "No active orders. Add AWB numbers to your Google Sheet's **Active** tab:\n\n"
                "`AWB Number | Customer Name | Phone Number`"
            )
        else:
            import pandas as pd
            df = pd.DataFrame(orders)

            display_cols = [c for c in [
                "AWB Number", "Customer Name", "Phone Number",
                "Last Status", "Last Checked", "Failed Attempts",
            ] if c in df.columns]

            def highlight(row):
                colors = []
                for col in row.index:
                    fa = row.get("Failed Attempts", 0)
                    if col == "Failed Attempts" and fa and int(fa) > 0:
                        colors.append("background-color: #ffcccc; color: red;")
                    else:
                        colors.append("")
                return colors

            st.dataframe(
                df[display_cols].style.apply(highlight, axis=1),
                use_container_width=True,
                hide_index=True,
            )

    with tab_delivered:
        delivered_orders = db.get_delivered_orders()
        if not delivered_orders:
            st.info("No delivered orders yet.")
        else:
            import pandas as pd
            df_d = pd.DataFrame(delivered_orders)
            display_cols_d = [c for c in [
                "AWB Number", "Customer Name", "Last Status", "Last Checked",
            ] if c in df_d.columns]
            st.dataframe(
                df_d[display_cols_d] if display_cols_d else df_d,
                use_container_width=True,
                hide_index=True,
            )

    # --- QUICK ACTIONS ---
    st.markdown("---")
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        if orders:
            awb_list = [str(r.get("AWB Number", "")) for r in orders]
            track_awb = st.selectbox("Re-track an AWB", awb_list, key="track_awb")
            if st.button("Track Now", key="track_btn"):
                from main import process_single_order
                with st.spinner(f"Checking {track_awb}..."):
                    row = next(r for r in orders if str(r.get("AWB Number", "")) == track_awb)
                    ok, msg = process_single_order(row, db=db)
                    if ok:
                        st.success(f"Result: {msg}")
                    else:
                        st.error(f"Result: {msg}")

    with col_b:
        if st.button("Test Slack", key="test_slack_btn"):
            from slack_notifier import test_slack_connection
            with st.spinner("Sending..."):
                if test_slack_connection():
                    st.success("Test message sent to Slack!")
                else:
                    st.error("Failed — check webhook URL in .env")

    with col_c:
        if st.button("Check DTDC API", key="test_dtdc_btn"):
            with st.spinner("Testing DTDC..."):
                ok, msg = test_dtdc_api()
                if ok:
                    st.success(f"DTDC API: {msg}")
                else:
                    st.error(f"DTDC API: {msg}")

    # --- SETTINGS ---
    st.markdown("---")
    with st.expander("Settings", expanded=False):
        st.subheader("Change Google Sheet")
        st.caption(f"Current Sheet ID: `{config.GOOGLE_SPREADSHEET_ID or 'Not set'}`")
        new_sheet_id = st.text_input(
            "New Google Sheet ID",
            placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
            key="new_sheet_id",
        )
        if new_sheet_id:
            col_test_sheet, col_save_sheet = st.columns(2)
            with col_test_sheet:
                if st.button("Test Connection", key="test_new_sheet"):
                    with st.spinner("Testing Google Sheets connection..."):
                        ok, msg = test_google_sheets(new_sheet_id)
                        if ok:
                            st.success(f"{msg}")
                        else:
                            st.error(f"Failed: {msg}")
                            if "403" in str(msg):
                                st.warning("Share the new Sheet with your service account email as Editor.")
            with col_save_sheet:
                if st.button("Save & Switch Sheet", key="save_new_sheet", type="primary"):
                    with st.spinner("Verifying and switching..."):
                        ok, msg = test_google_sheets(new_sheet_id)
                        if ok:
                            write_env_file({"GOOGLE_SPREADSHEET_ID": new_sheet_id})
                            _reload_config()
                            st.success(f"Switched to: {msg}")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Cannot switch — connection failed: {msg}")

        st.markdown("---")
        st.subheader("Change Slack Webhook")
        st.caption(f"Current: `{'Configured' if config.SLACK_WEBHOOK_URL and 'hooks.slack.com' in config.SLACK_WEBHOOK_URL else 'Not set'}`")
        new_slack_url = st.text_input(
            "New Slack Webhook URL",
            placeholder="https://hooks.slack.com/services/T.../B.../xxx",
            key="new_slack_url",
        )
        if new_slack_url:
            col_test_slack, col_save_slack = st.columns(2)
            with col_test_slack:
                if st.button("Test Webhook", key="test_new_slack"):
                    with st.spinner("Sending test message..."):
                        ok, msg = test_slack_webhook(new_slack_url)
                        if ok:
                            st.success("Connected! Check your Slack channel.")
                        else:
                            st.error(f"Failed: {msg}")
            with col_save_slack:
                if st.button("Save Webhook", key="save_new_slack", type="primary"):
                    if "hooks.slack.com" not in new_slack_url:
                        st.error("Invalid URL — must start with https://hooks.slack.com/services/")
                    else:
                        write_env_file({"SLACK_WEBHOOK_URL": new_slack_url, "SLACK_ENABLED": "True"})
                        _reload_config()
                        st.success("Slack webhook updated!")
                        time.sleep(1)
                        st.rerun()

        st.markdown("---")
        st.subheader("Custom Slack Messages")
        st.caption(
            "Customize the messages sent to Slack. Use these placeholders: "
            "`{order_id}`, `{customer}`, `{awb}`, `{old_status}`, `{new_status}`"
        )

        # Load current custom messages from state
        _state = db.load_system_state()
        current_delivered_msg = _state.get("custom_msg_delivered", "")
        current_status_msg = _state.get("custom_msg_status_change", "")

        delivered_msg = st.text_area(
            "Delivered Message",
            value=current_delivered_msg,
            placeholder="e.g., Hey {customer}, your order {order_id} (AWB: {awb}) has been delivered!",
            key="custom_delivered_msg",
            height=80,
        )

        status_msg = st.text_area(
            "Status Change Message",
            value=current_status_msg,
            placeholder="e.g., Hi {customer}, your shipment {awb} moved from {old_status} to {new_status}.",
            key="custom_status_msg",
            height=80,
        )

        if st.button("Save Messages", key="save_custom_msgs", type="primary"):
            db.update_system_state({
                "custom_msg_delivered": delivered_msg,
                "custom_msg_status_change": status_msg,
            })
            st.success("Custom messages saved!")

        # --- Preview ---
        st.markdown("**Preview** _(with sample data)_")
        sample = {
            "order_id": "ORD-1234",
            "customer": "Rahul Sharma",
            "awb": "X98765432",
            "old_status": "In Transit",
            "new_status": "Out for Delivery",
        }
        sample_delivered = {
            "order_id": "ORD-1234",
            "customer": "Rahul Sharma",
            "awb": "X98765432",
            "old_status": "Out for Delivery",
            "new_status": "Delivered",
        }

        col_prev1, col_prev2 = st.columns(2)
        with col_prev1:
            st.markdown("**Status Change**")
            if status_msg:
                preview_status = (status_msg
                    .replace("{order_id}", sample["order_id"])
                    .replace("{customer}", sample["customer"])
                    .replace("{awb}", sample["awb"])
                    .replace("{old_status}", sample["old_status"])
                    .replace("{new_status}", sample["new_status"]))
                st.info(preview_status)
            else:
                st.caption("_No custom message — default Slack notification will be used._")

        with col_prev2:
            st.markdown("**Delivered**")
            if delivered_msg:
                preview_delivered = (delivered_msg
                    .replace("{order_id}", sample_delivered["order_id"])
                    .replace("{customer}", sample_delivered["customer"])
                    .replace("{awb}", sample_delivered["awb"])
                    .replace("{old_status}", sample_delivered["old_status"])
                    .replace("{new_status}", sample_delivered["new_status"]))
                st.success(preview_delivered)
            else:
                st.caption("_No custom message — default Slack notification will be used._")

    # --- LOGS ---
    st.markdown("---")
    with st.expander("System Logs", expanded=False):
        logs = get_recent_logs(25)
        st.code("".join(logs) or "No logs yet.", language="text")

    # Auto-refresh every 60 seconds
    st.markdown("---")
    col_refresh, col_auto = st.columns([1, 3])
    with col_refresh:
        if st.button("Refresh", key="refresh"):
            st.rerun()
    with col_auto:
        auto_refresh = st.checkbox("Auto-refresh (60s)", value=False, key="auto_refresh")

    if auto_refresh:
        time.sleep(60)
        st.rerun()


# ============================================================
# ENTRY POINT
# ============================================================
if not is_setup_complete():
    run_setup_wizard()
else:
    google_auth_gate()
    run_dashboard()
