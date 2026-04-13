import requests
import config
from logger import log_info, log_error, log_warning
import time

# DTDC's official tracking API (free, no auth required)
DTDC_API_URL = "https://www.dtdc.com/wp-json/custom/v1/domestic/track"

def fetch_dtdc_status(awb_number):
    """
    Calls DTDC's official JSON API directly. No browser needed.
    Returns: (success_boolean, status_string_or_error_message)
    """
    try:
        log_info(f"Fetching status for AWB {awb_number} via DTDC API...")

        resp = requests.post(
            DTDC_API_URL,
            json={"trackType": "shipment", "trackNumber": str(awb_number)},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Content-Type": "application/json",
                "Referer": "https://www.dtdc.com/track-your-shipment/",
            },
            timeout=15,
        )

        if resp.status_code != 200:
            return False, f"DTDC API returned HTTP {resp.status_code}"

        data = resp.json()

        # API-level error
        if data.get("statusCode") != 200 or data.get("errorMessage"):
            error = data.get("errorMessage") or data.get("statusDescription", "Unknown error")
            return False, f"DTDC API error: {error}"

        header = data.get("header", {})
        if not header:
            return False, "DTDC API returned empty header - AWB may be invalid"

        current_status = header.get("currentStatusDescription", "").strip()
        if not current_status:
            return False, "No status description returned for this AWB"

        # Build a rich status string with key details
        status_date = header.get("currentStatusDate", "")
        status_time = header.get("currentStatusTime", "")
        origin = header.get("originCity", "")
        destination = header.get("destinationCity", "")
        receiver = header.get("receiverName", "").strip()

        parts = [current_status]
        if status_date:
            timestamp = f"{status_date} {status_time}".strip().rstrip(".0")
            parts.append(f"as of {timestamp}")
        if origin and destination:
            parts.append(f"({origin} -> {destination})")
        if current_status == "Delivered" and receiver:
            parts.append(f"[received by: {receiver}]")

        status_text = " | ".join(parts)
        log_info(f"Successfully fetched AWB {awb_number}: {current_status}")
        return True, status_text

    except requests.exceptions.Timeout:
        log_error(f"DTDC API request timed out for AWB {awb_number}")
        return False, "DTDC API request timed out"
    except requests.exceptions.ConnectionError as e:
        log_error(f"Connection error for AWB {awb_number}: {str(e)}")
        return False, f"Connection error: {str(e)}"
    except Exception as e:
        log_error(f"Error fetching AWB {awb_number}: {str(e)}")
        return False, f"API error: {str(e)}"


# Keep old Playwright scraper as a fallback
def scrape_dtdc_status_browser(awb_number):
    """
    Fallback: scrapes TrackCourier.io using Playwright if the DTDC API is down.
    Returns: (success_boolean, status_string_or_error_message)
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    except ImportError:
        return False, "Playwright not installed - browser fallback unavailable"

    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=config.HEADLESS_BROWSER, channel="msedge")
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            log_info(f"[Fallback] Opening TrackCourier.io for AWB {awb_number}...")
            page.goto("https://trackcourier.io/dtdc-tracking", timeout=45000)

            try:
                page.wait_for_selector('#trackingNumber', timeout=10000)
                page.fill('#trackingNumber', str(awb_number))
                log_info("Filled AWB. Clicking Track...")
                page.click('button[onclick="onFormSubmit()"]')
            except PlaywrightTimeoutError:
                with open("failure.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                raise Exception("Failed to load TrackCourier input field. Dumped to failure.html")

            time.sleep(4)

            try:
                page.wait_for_selector('.checkpoints, .tracking-result, .status, .card, table', timeout=15000)
            except PlaywrightTimeoutError:
                if "No tracking details" in page.content() or "Not Found" in page.content():
                    return False, "Invalid AWB Number or No Details Found"
                raise Exception("Could not find the status text after tracking on TrackCourier.")

            elements = page.locator('.checkpoint__content, .status, .tag-delivered, .tag-intransit, td').all_inner_texts()
            if not elements:
                status_text = page.locator('.checkpoints, .tracking-result, .card').last.text_content().strip()
            else:
                status_text = " | ".join([e.strip() for e in elements if e.strip()])[0:500]

            no_info_phrases = ["no information is available", "no tracking details", "not found", "invalid", "no record"]
            if any(phrase in status_text.lower() for phrase in no_info_phrases):
                return False, f"No tracking data available for this AWB: {status_text[:200]}"

            log_info(f"[Fallback] Successfully scraped AWB {awb_number}")
            return True, status_text

        except Exception as e:
            log_error(f"[Fallback] Error scraping AWB {awb_number}: {str(e)}")
            return False, f"Browser scraping error: {str(e)}"
        finally:
            if browser:
                browser.close()


def get_status_with_retry(awb_number):
    """
    Tries the fast DTDC API first. Falls back to browser scraping if the API fails.
    Applies retry logic on each method.
    """
    # --- Primary: DTDC direct API ---
    last_error = None
    for attempt in range(1, config.RETRY_LIMIT + 1):
        success, result = fetch_dtdc_status(awb_number)
        if success:
            return True, result

        last_error = result
        if attempt < config.RETRY_LIMIT:
            wait_time = attempt * 2  # Shorter waits for API (2s, 4s)
            log_warning(f"API retry for AWB {awb_number} in {wait_time}s... (Attempt {attempt + 1}/{config.RETRY_LIMIT})")
            time.sleep(wait_time)

    # --- Fallback: Browser scraping ---
    log_warning(f"DTDC API failed for AWB {awb_number} after {config.RETRY_LIMIT} attempts. Trying browser fallback...")
    success, result = scrape_dtdc_status_browser(awb_number)
    if success:
        return True, result

    # Both methods failed
    return False, f"API error: {last_error} | Browser fallback: {result}"
