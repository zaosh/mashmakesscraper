# MashMakes Tracker

Automated DTDC shipment tracking with Slack notifications. Your team adds AWB numbers to a Google Sheet from any device — the system tracks them, sends status updates to Slack, and auto-clears delivered orders.

## Setup

```
git clone https://github.com/zaosh/mashmakesscraper.git
cd mashmakesscraper
install.bat
```

`install.bat` installs all required dependencies. Once done, run `run.bat` to start the system. Open the URL shown in the terminal (usually `http://localhost:8501`) and follow the on-screen setup wizard.

## How It Works

1. **Your team adds AWB numbers** to a shared Google Sheet (from phone, laptop, anywhere)
2. **Every 3 hours**, the system checks each AWB against DTDC's tracking API
3. **Status changes** trigger a Slack notification to your team's channel
4. **Delivered orders** are automatically moved to a "Delivered" tab
5. **Daily summary** sent to Slack at 6 PM
6. **Error alerts** sent immediately if tracking breaks

## What You Need

- **Python 3.10+**
- **A Google account** (to create a Google Sheet and service account)
- **A Slack workspace** (to receive notifications)
- That's it. No paid APIs, no databases to set up.

## Project Structure

```
├── main.py              # Background scheduler (runs every 3 hours)
├── dashboard.py         # Streamlit UI with setup wizard
├── scraper.py           # DTDC tracking API + browser fallback
├── database.py          # Google Sheets read/write
├── slack_notifier.py    # Slack notifications (status, errors, summaries)
├── sms.py               # Optional SMS notifications (Twilio/Fast2SMS)
├── setup_manager.py     # First-time setup logic
├── config.py            # Environment config loader
├── logger.py            # Logging
├── requirements.txt     # Python dependencies
└── data/                # Local logs and system state
```

## Google Sheet Format

The system auto-creates two tabs in your sheet:

**Active** (your team fills in the first 3 columns):

| AWB Number | Customer Name | Phone Number | Last Status | Last Checked | Status Changes | SMS Sent | Failed Attempts |
|---|---|---|---|---|---|---|---|
| X12345678 | John | 9876543210 | *(auto-filled)* | *(auto-filled)* | *(auto-filled)* | *(auto-filled)* | *(auto-filled)* |

**Delivered** (auto-populated when orders are delivered — no action needed)

## Slack Notifications

The system sends these to your channel:

- **Status updates** — when a shipment moves (e.g., "In Transit" → "Out for Delivery")
- **Batch reports** — after each tracking run (X succeeded, Y failed)
- **Error alerts** — when tracking fails for a specific AWB
- **Scraper collapse** — urgent alert if ALL orders fail (with troubleshooting steps)
- **Daily summary** — end-of-day report at 6 PM

## Recent Fixes

- Auto-reconnects to Google Sheets when auth token expires
- Row operations now find rows by AWB value instead of index (safe with concurrent edits)
- Sheet updates batched into single API calls (avoids Google rate limits)
- DB connection is lazy-initialized (no longer breaks if config isn't ready at import)
- System state file writes atomically (no corruption if read during write)
- Log files auto-rotate at 5 MB (won't fill disk)
- Dashboard correctly shows "Awaiting first run" instead of error on fresh setups

## Running 24/7 on a Server

- Auto-reconnects to Google Sheets without manual intervention
- Survives token expiry, network blips, and API downtime gracefully
- Log rotation prevents disk from filling up
- Immediate Slack alerts if the tracker goes down
- Daily summary reports at 6 PM
- Auto-restarts on reboot with pm2:

```bash
npm install -g pm2
pm2 start main.py --name "tracker" --interpreter python3
pm2 start "streamlit run dashboard.py --server.port 80" --name "dashboard"
pm2 save && pm2 startup
```

## Troubleshooting

| Problem | Fix |
|---|---|
| "Not connected to Google Sheets" | Check that `service_account.json` exists and the sheet is shared with the service account email |
| Slack messages not arriving | Verify webhook URL in `.env`, run "Test Slack" from dashboard |
| All AWBs failing | DTDC API may be down — system auto-retries. Check `data/system.log` |
| "No tracking data for this AWB" | The AWB may not be in DTDC's system yet. It will be picked up on the next run |
