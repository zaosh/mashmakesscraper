import sys
sys.stdout.reconfigure(encoding='utf-8')
from scraper import get_status_with_retry

def run_test():
    print("--- DTDC Scraper Live Test ---")
    
    if len(sys.argv) > 1:
        awb = sys.argv[1]
    else:
        awb = input("Enter DTDC AWB Number: ").strip()
        
    if not awb:
        print("Error: No AWB provided.")
        return

    print(f"Starting test for AWB: {awb}...")
    print("Please wait up to 30 seconds for the headless browser to load and scrape...")
    
    success, result = get_status_with_retry(awb)
    
    print("\n--- TEST RESULTS ---")
    if success:
        print("✅ SUCCESS")
        print(f"Extracted Status Payolad: {result}")
    else:
        print("❌ FAILED")
        print(f"Error Message: {result}")
        print("\nNote: If this is failing, ensure the DTDC website hasn't changed its layout (check scraper.py input selectors).")

if __name__ == "__main__":
    run_test()
