# MashMakes Tracker

Automated DTDC shipment tracking with Slack notifications. Your team adds AWB numbers to a Google Sheet from any device — the system tracks them, sends status updates to Slack, and auto-clears delivered orders.

## How It Works

1. **Your team adds AWB numbers** to a shared Google Sheet (from phone, laptop, anywhere)
2. **Every 3 hours**, the system checks each AWB against DTDC's tracking API
3. **Status changes** trigger a Slack notification to your team's channel
4. **Delivered orders** are automatically moved to a "Delivered" tab
5. **Daily summary** sent to Slack at 6 PM
6. **Error alerts** sent immediately if tracking breaks

## Quick Install (5 minutes)

### 1. Clone and install

```bash
git clone https://github.com/zaosh/mashmakesscraper.git
cd mashmakesscraper
pip install -r requirements.txt
```

### 2. Run the setup wizard

```bash
streamlit run dashboard.py
```

Open the URL it shows (usually `http://localhost:8501`) and follow the on-screen setup. The wizard walks you through:

- **Google Sheets** — creating a service account and connecting your sheet (step-by-step instructions included on screen)
- **Slack** — creating a webhook and connecting your channel (step-by-step instructions included on screen)
- **System check** — verifies everything works before going live

### 3. Start the background tracker

After setup, open a second terminal and run:

```bash
python main.py
```

This runs the tracking loop. Leave it running in the background (or use a process manager like PM2).

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

## Deploying on a Server (Optional)

To keep it running without your laptop:

```bash
# Install pm2
npm install -g pm2

# Start both processes
pm2 start main.py --name "tracker" --interpreter python3
pm2 start "streamlit run dashboard.py --server.port 80" --name "dashboard"

# Auto-restart on reboot
pm2 save && pm2 startup
```

## Troubleshooting

| Problem | Fix |
|---|---|
| "Not connected to Google Sheets" | Check that `service_account.json` exists and the sheet is shared with the service account email |
| Slack messages not arriving | Verify webhook URL in `.env`, run "Test Slack" from dashboard |
| All AWBs failing | DTDC API may be down — system auto-retries. Check `data/system.log` |
| "No tracking data for this AWB" | The AWB may not be in DTDC's system yet. It will be picked up on the next run |
