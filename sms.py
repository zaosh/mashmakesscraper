import requests
from twilio.rest import Client
import config
from logger import log_info, log_error, log_warning

def send_twilio_sms(to_number, message):
    if not config.TWILIO_ACCOUNT_SID or not config.TWILIO_AUTH_TOKEN:
        log_error("Twilio credentials not configured.")
        return False
        
    try:
        client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        # Twilio requires numbers to have country code, typically handled by adding +
        if not to_number.startswith('+'):
            to_number = '+' + to_number
            
        msg = client.messages.create(
            body=message,
            from_=config.TWILIO_FROM_NUMBER,
            to=to_number
        )
        log_info(f"Twilio SMS sent to {to_number}, SID: {msg.sid}")
        return True
    except Exception as e:
        log_error(f"Twilio SMS failed to {to_number}: {str(e)}")
        return False

def send_fast2sms(to_number, message):
    if not config.FAST2SMS_API_KEY:
        log_error("Fast2SMS API key not configured.")
        return False
        
    try:
        url = "https://www.fast2sms.com/dev/bulkV2"
        # Removing any + or non-numeric characters for Fast2SMS (usually 10 digits in India)
        to_number = ''.join(filter(str.isdigit, to_number))
        if len(to_number) > 10 and to_number.startswith("91"):
            to_number = to_number[2:]
            
        payload = {
            "route": "v3",
            "sender_id": "TXTIND",
            "message": message,
            "language": "english",
            "flash": 0,
            "numbers": to_number,
        }
        headers = {
            "authorization": config.FAST2SMS_API_KEY,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        response = requests.post(url, data=payload, headers=headers)
        res_json = response.json()
        
        if res_json.get("return"):
            log_info(f"Fast2SMS sent to {to_number}")
            return True
        else:
            log_error(f"Fast2SMS failed to {to_number}: {res_json}")
            return False
    except Exception as e:
        log_error(f"Fast2SMS request failed: {str(e)}")
        return False

def send_customer_update(order_id, customer_name, to_number, status, awb):
    tracking_link = f"https://www.dtdc.in/tracking/shipment-tracking.asp" # Generic tracking url
    msg = f"Hi {customer_name}, your MashMakes order (#{order_id}) is now: {status}. Track AWB {awb} at dtdc.in"
    
    log_info(f"Attempting to send SMS for order {order_id}...")
    if config.ACTIVE_SMS_PROVIDER == "TWILIO":
        return send_twilio_sms(to_number, msg)
    else:
        return send_fast2sms(to_number, msg)

def alert_admin(issue_description):
    """Sends a critical alert to the admin."""
    if not config.ADMIN_PHONE:
        log_warning("Admin phone not set. Admin alert skipped.")
        return False
        
    msg = f"⚠️ ANTIGRAVITY ALERT\n{issue_description}\nPlease check the tracker dashboard."
    
    log_info(f"Sending Admin Alert: {issue_description}")
    if config.ACTIVE_SMS_PROVIDER == "TWILIO":
        return send_twilio_sms(config.ADMIN_PHONE, msg)
    else:
        return send_fast2sms(config.ADMIN_PHONE, msg)
