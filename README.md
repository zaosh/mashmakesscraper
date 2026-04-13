# MashMakes Tracker

Automated DTDC shipment tracking system. Your team adds AWB numbers to a shared Google Sheet — the system tracks them every 3 hours, posts status updates to Slack, and auto-clears delivered orders.

## Setup

```
git clone https://github.com/zaosh/mashmakesscraper.git
cd mashmakesscraper
install.bat
```

`install.bat` installs all required dependencies. Once done, run `run.bat` to start the system. Open the URL shown in the terminal (usually `http://localhost:8501`) and follow the on-screen setup wizard.

## How It Works

1. Your team adds AWB numbers to the Google Sheet's **Active** tab (from any device)
2. Every 3 hours, the system checks each AWB against DTDC's tracking API
3. Status changes trigger a Slack notification to your team's channel
4. Delivered orders are automatically moved to the **Delivered** tab
5. A daily summary is sent to Slack at 6 PM
6. If the tracker breaks, Slack gets an immediate alert with troubleshooting steps

The dashboard at `http://localhost:8501` shows live order status, system health, and logs.
