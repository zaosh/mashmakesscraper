# AI Context: Antigravity Shipment Tracker

## 📌 Project Purpose
A lightweight, production-ready internal tool to automate DTDC shipment tracking and trigger SMS notifications. It provides a Streamlit dashboard for a non-technical operations team to monitor health, override statuses, and view logs.

## 🛠 Tech Stack
- **Language**: Python 3.10+
- **Scraping**: `playwright` (Sync API) used headless. No paid APIs are used.
- **UI**: `streamlit` for the dashboard (`dashboard.py`).
- **Data Storage**: Local CSV (`data/orders.csv`) & JSON (`data/system_state.json`). Simple, robust, intentionally avoids heavy SQL databases.
- **Messaging**: `twilio` and `requests` (Fast2SMS).
- **Scheduling**: `schedule` library running in a blocked `while` loop within `main.py`.

## 📂 Architecture Rules
1. **Separation of Concerns:**
   - `scraper.py` handles Playwright interactions *only*.
   - `sms.py` handles notification logic *only*.
   - `database.py` safely mutates `orders.csv` without locking it against user MS Excel edits.
   - `main.py` is the autonomous headless orchestration loop.
   - `dashboard.py` is the read/manual-override Streamlit UI.

2. **Error Handling philosophy:**
   - Always auto-retry up to 3 times before failing an order completely.
   - Log human-readable errors using `logger.py`.
   - Alert the `ADMIN_PHONE` via SMS if 100% of batch trackings fail (indicating DTDC HTML layout changed).

3. **Modifications:** 
   - Keep the system easy to start (just `python main.py` and `streamlit run dashboard.py`).
   - Prioritize reliability over fast performance. Random delays between AWB checks are encouraged to prevent IP bans.
