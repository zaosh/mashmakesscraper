# 🛠 Antigravity System Troubleshooting Guide

This guide is designed for the operations team to diagnose and fix common issues with the shipment tracking system.

## 1. Issue: "Tracking system failed to run" or "Scraping failed"

**Problem:** Scraper fails on all orders and the System Health dashboard shows `❌ Scraper: Failing`.
**Cause:** DTDC changed the design or layout of their website, so the robot cannot find the tracking input box or the track button.
**Solution:**
1. Open the file `scraper.py` using a simple text editor (like Notepad).
2. Locate the line that looks like this:
   `input_selector = 'textarea[name="trackingNo"]'`
3. Look for the real tracker by opening `www.dtdc.in` in your browser. Right-click the tracking input field, click "Inspect", and find the id or name property.
4. Update `input_selector` with the new value. (e.g. `input_selector = 'input[id="newTrackerId"]'`).
5. Save the file and click "Re-run Tracking for this Order" on the dashboard to test if it works.

## 2. Issue: SMS are not reaching customers

**Problem:** Dashboard shows `SMS Sent = No` for valid updates, or you see "SMS Auth Error" in the Recent Logs.
**Cause:** 
- The SMS API token has expired.
- You have run out of credits with Fast2SMS or Twilio.
- The user's phone number in `orders.csv` is incorrect.
**Solution:** 
1. Open the `.env` file using a text editor.
2. Ensure your `FAST2SMS_API_KEY` (or Twilio credentials) hasn't expired. If you generate a new one, replace the old value in `.env`.
3. Restart the dashboard terminal for the new `.env` settings to take effect.
4. If it's a number format issue, manually correct the `Phone Number` in Excel and then use the dashboard's "Manually Resend SMS" button.

## 3. Issue: An order is stuck on 'Failed' in the dashboard

**Problem:** An order is permanently highlighted RED and the system won't track it anymore. The 'Failed Attempts' count is 3.
**Cause:** The tracking page on DTDC repeatedly failed to load this specific AWB (invalid tracking ID, tracking ID doesn't exist yet, or network timeout).
**Solution:**
1. Manually verify the tracking ID on the DTDC website.
2. If the Tracking ID is wrong, update `orders.csv` with the correct ID.
3. On the Dashboard, go to "Manual Overrides", pick the Order ID, and click "Re-run Tracking". It will reset the failure count and force a track if it's successful.

## 4. Issue: "Orders.csv being used by another process"

**Problem:** The logs say `Permission denied: orders.csv`.
**Cause:** Someone has `orders.csv` open in Microsoft Excel and the bot is trying to update it at the same time.
**Solution:**
1. Please ensure that operations teams *close* Excel after making changes to the `.csv` file. 
2. The tracker will retry the file write operation on its next 3-hour scheduled run.
