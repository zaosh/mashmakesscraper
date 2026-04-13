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

st.set_page_config(page_title="MashMakes Tracker — Setup 01", page_icon="📦", layout="wide")


# ============================================================
# GOOGLE AUTH LOGIN
# ============================================================
def google_auth_gate():
    """
    Google OAuth login gate.
    Only allows users with emails from the configured allowed domain.
    Uses Streamlit's experimental user info from OAuth proxy.
    """
    # If no auth configured, allow access (for local dev)
    allowed_emails = os.getenv("ALLOWED_EMAILS", "")
    allowed_domain = os.getenv("ALLOWED_DOMAIN", "")

    if not allowed_emails and not allowed_domain:
        return True

    # Check if Streamlit has user info (requires OAuth proxy like Cloudflare Access,
    # Google IAP, or streamlit-authenticator)
    user_email = st.experimental_user.get("email", "") if hasattr(st, "experimental_user") else ""

    if not user_email:
        st.title("🔒 Access Restricted")
        st.error(
            "This dashboard requires Google authentication.\n\n"
            "Please access this through your company's SSO portal, "
            "or ask your admin to add your email to ALLOWED_EMAILS in .env"
        )
        st.stop()
        return False

    # Check domain
    if allowed_domain and not user_email.endswith(f"@{allowed_domain}"):
        st.title("🔒 Access Denied")
        st.error(f"Your email ({user_email}) is not from the allowed domain (@{allowed_domain}).")
        st.stop()
        return False

    # Check specific emails
    if allowed_emails:
        email_list = [e.strip().lower() for e in allowed_emails.split(",")]
        if user_email.lower() not in email_list:
            st.title("🔒 Access Denied")
            st.error(f"Your email ({user_email}) is not in the allowed list.")
            st.stop()
            return False

    return True


# ============================================================
# FIRST-TIME SETUP WIZARD
# ============================================================
def run_setup_wizard():
    st.title("📦 MashMakes Tracker — Setup")
    st.markdown("Let's get your shipment tracking system running. This takes about 5 minutes.")
    st.markdown("---")

    if "setup_step" not in st.session_state:
        st.session_state["setup_step"] = 1

    step = st.session_state["setup_step"]

    # Progress bar
    st.progress(step / 3)

    # ---- STEP 1: Google Sheets ----
    if step == 1:
        st.header("Step 1 of 3 — Connect Google Sheets")

        st.markdown("""
**This is your team's shared database.** Anyone with access to the Google Sheet can add
AWB numbers from any device (phone, laptop, tablet). The system watches the sheet,
tracks each shipment, sends updates to Slack, and auto-clears delivered orders.
""")

        # --- PART A: Create the Google Sheet ---
        st.subheader("A. Create your Google Sheet")
        st.markdown("""
1. Open [Google Sheets](https://sheets.google.com) and create a **new blank spreadsheet**
2. Name it something like **"MashMakes Shipments"**
3. **Copy the Sheet ID from the URL bar** — it's the long random string:

   `https://docs.google.com/spreadsheets/d/`**`THIS_PART_IS_THE_ID`**`/edit`

   For example, if your URL is:
   `https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit`

   Then the Sheet ID is: `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms`
""")

        sheet_id = st.text_input(
            "Paste your Google Sheet ID here",
            placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
            key="w_sheet_id",
        )

        st.markdown("---")

        # --- PART B: Create a Service Account ---
        st.subheader("B. Create a Service Account (one-time, ~3 minutes)")
        st.markdown("""
A "service account" is like a robot Google account that lets this system read and write
to your Sheet. You create it once and never have to touch it again.

**Follow these steps:**
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
- Wait a few seconds for it to activate

**3. Create the Service Account**
- In the search bar, type **"Service Accounts"** and click the result under IAM
- Click **"+ Create Service Account"** at the top
- Name: `antigravity-tracker` (or anything you like)
- Click **Create and Continue**
- For "Role", select **Editor** from the dropdown, then click **Continue**
- Click **Done**

**4. Download the Key File**
- You'll see your new service account in the list. Click on it
- Go to the **"Keys"** tab
- Click **"Add Key" → "Create new key"**
- Choose **JSON** and click **Create**
- A `.json` file will download to your computer — **this is what you upload below**

**5. Share your Google Sheet with the service account**
- Open the downloaded JSON file in Notepad
- Find the line that says `"client_email": "something@something.iam.gserviceaccount.com"`
- Copy that email address
- Go to your Google Sheet, click **Share**, paste the email, give it **Editor** access
""")

        st.warning("""
**Keep the JSON file safe.** It's like a password for your Google Sheet.
Don't share it publicly or send it over chat. Upload it here and it stays on this server only.
""")

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
                        f"`{sa_email}` as an **Editor**. "
                        f"(Open your Sheet → Share → paste this email → Editor → Send)"
                    )
                else:
                    st.error("This file doesn't look right — it's missing a `client_email` field. "
                             "Make sure you downloaded the JSON key from the Service Accounts page.")
            except Exception:
                st.error("Couldn't read this file. Make sure it's the .json file that Google downloaded for you.")

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
                                st.warning(
                                    "**Permission denied.** This usually means you haven't shared "
                                    "the Google Sheet with the service account email yet. "
                                    "Go to your Sheet → Share → paste the service account email → Editor → Send."
                                )
                            elif "not found" in str(msg).lower():
                                st.warning(
                                    "**Sheet not found.** Double-check the Sheet ID you pasted. "
                                    "It should be the long string from the URL, not the full URL."
                                )
                else:
                    st.warning("Upload the JSON file and enter the Sheet ID first.")

        with col_next:
            if st.button("Next →", key="step1_next"):
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
- Status change alerts (e.g., "In Transit" → "Out for Delivery")
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
- Click **"Create New App"**
- Choose **"From scratch"**
- App Name: `MashMakes Tracker` (or anything you like)
- Pick your **workspace** from the dropdown
- Click **"Create App"**

**3. Enable Webhooks**
- On the left sidebar, click **"Incoming Webhooks"**
- Toggle the switch to **ON**
- Scroll down and click **"Add New Webhook to Workspace"**
- Pick the **channel** where you want shipment updates (e.g., `#shipments` or `#operations`)
- Click **"Allow"**

**4. Copy the URL**
- You'll see a new webhook URL that looks like:
  `https://hooks.slack.com/services/TXXXXX/BXXXXX/XXXXXXXXXX`
- Click **"Copy"** and paste it below
""")

        st.warning("""
**Keep this URL private.** Anyone with this URL can post messages to your Slack channel.
- Don't paste it in Slack itself or any public place
- It's stored in a local config file on this server only
- If it leaks, go back to the Slack App settings and regenerate it
""")

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
                            st.warning("The URL doesn't look right. Make sure you copied the full URL starting with `https://hooks.slack.com/services/`")

        col_back, col_next = st.columns(2)
        with col_back:
            if st.button("← Back", key="step2_back"):
                st.session_state["setup_step"] = 1
                st.rerun()
        with col_next:
            if st.button("Next →", key="step2_next"):
                if not webhook_url:
                    st.error("Slack webhook is required — this is how your team gets updates.")
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
            st.warning("The DTDC API is not reachable. The system will fall back to browser scraping, which is slower but still works.")

        # Google Sheets
        sheet_id = st.session_state.get("cfg_sheet_id", "")
        with st.spinner("Testing Google Sheets..."):
            gs_ok, gs_msg = test_google_sheets(sheet_id)
        if gs_ok:
            st.success(f"Google Sheets: {gs_msg}")
        else:
            st.error(f"Google Sheets: {gs_msg}")

        # Slack
        st.success("Slack: Configured")

        st.markdown("---")
        st.subheader("How the system works")
        st.markdown("""
1. **Your team adds AWB numbers** to the Google Sheet's "Active" tab (from any device)
2. **Every 3 hours**, the system reads the sheet and checks each AWB against DTDC
3. **When a status changes**, it updates the sheet and sends a Slack notification
4. **When an order is delivered**, it auto-moves to the "Delivered" tab (keeps Active clean)
5. **At 6 PM daily**, it sends a summary report to Slack
6. **If things break**, it alerts Slack immediately with troubleshooting steps
""")

        st.markdown("---")
        st.subheader("Security Summary")
        st.markdown("""
- **Google Sheet** — access controlled by Google (only shared accounts can read/write)
- **Slack Webhook** — stored in local `.env` file, never transmitted elsewhere
- **Service Account Key** — stored locally as `service_account.json`, not committed to git
- **DTDC API** — public endpoint, no credentials needed
- **No passwords stored** — access is controlled via Google Sheet sharing permissions
""")

        col_back, col_finish = st.columns(2)
        with col_back:
            if st.button("← Back", key="step3_back"):
                st.session_state["setup_step"] = 2
                st.rerun()
        with col_finish:
            if st.button("Complete Setup", type="primary", key="finish_setup"):
                env_vars = {
                    "GOOGLE_SPREADSHEET_ID": sheet_id,
                    "GOOGLE_SERVICE_ACCOUNT_FILE": "service_account.json",
                    "SLACK_WEBHOOK_URL": st.session_state["cfg_slack_url"],
                    "SLACK_ENABLED": "True",
                    "HEADLESS_BROWSER": "True",
                    "RETRY_LIMIT": "3",
                }
                write_env_file(env_vars)
                mark_setup_complete()

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
    st.title("📦 MashMakes Shipment Tracker")

    db = DatabaseManager()

    # --- SYSTEM HEALTH ---
    state = db.load_system_state()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        s = state.get("scraper_status", "Unknown")
        if s == "Working":
            st.success(f"Scraper: {s}")
        elif s == "Warning":
            st.warning(f"Scraper: {s}")
        else:
            st.error(f"Scraper: {s}")
    with col2:
        if config.SLACK_ENABLED and config.SLACK_WEBHOOK_URL:
            st.success("Slack: Connected")
        else:
            st.warning("Slack: Not set")
    with col3:
        st.info(f"Last Run: {state.get('last_run', 'Never')}")
    with col4:
        st.metric("Today", f"{state.get('success_today', 0)} ok / {state.get('failed_today', 0)} failed")

    st.markdown("---")

    # --- ACTIVE ORDERS ---
    if not db.is_connected():
        st.error("Not connected to Google Sheets. Check your service account file and Sheet ID.")
        st.stop()

    orders = db.get_orders()
    delivered_count = db.get_delivered_count()

    st.header(f"Active Orders ({len(orders)})")
    st.caption(f"{delivered_count} orders delivered and auto-cleared")

    if not orders:
        st.info(
            "No active orders. Add AWB numbers to your Google Sheet's **Active** tab:\n\n"
            "`AWB Number | Customer Name | Phone Number`"
        )
    else:
        import pandas as pd
        df = pd.DataFrame(orders)

        # Highlight problems
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
            df.style.apply(highlight, axis=1),
            use_container_width=True,
            hide_index=True,
        )

    # --- QUICK ACTIONS ---
    st.markdown("---")
    col_a, col_b = st.columns(2)

    with col_a:
        if orders:
            awb_list = [str(r.get("AWB Number", "")) for r in orders]
            track_awb = st.selectbox("Re-track an AWB", awb_list, key="track_awb")
            if st.button("Track Now", key="track_btn"):
                from main import process_single_order
                with st.spinner(f"Checking {track_awb}..."):
                    row = next(r for r in orders if str(r.get("AWB Number", "")) == track_awb)
                    ok, msg = process_single_order(row)
                    st.success(f"Result: {msg}") if ok else st.error(f"Result: {msg}")

    with col_b:
        if st.button("Test Slack", key="test_slack_btn"):
            from slack_notifier import test_slack_connection
            with st.spinner("Sending..."):
                if test_slack_connection():
                    st.success("Test message sent to Slack!")
                else:
                    st.error("Failed — check webhook URL in .env")

    # --- LOGS ---
    st.markdown("---")
    with st.expander("System Logs", expanded=False):
        logs = get_recent_logs(25)
        st.code("".join(logs) or "No logs yet.", language="text")

    if st.button("Refresh", key="refresh"):
        st.rerun()


# ============================================================
# ENTRY POINT
# ============================================================
if not is_setup_complete():
    run_setup_wizard()
else:
    google_auth_gate()
    run_dashboard()
