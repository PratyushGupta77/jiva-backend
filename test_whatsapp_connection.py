import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

# Hardcoded recipient for testing (You can change this)
# The test number must be added in the Meta Dashboard if using a test account.
RECIPIENT_PHONE = "919319108107" 

def test_send_message():
    print("--- WhatsApp Connection Test ---")
    print(f"Phone ID: {WHATSAPP_PHONE_ID}")
    print(f"Token: {WHATSAPP_TOKEN[:10]}..." if WHATSAPP_TOKEN else "Token: MISSING")

    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print("❌ Error: Missing credentials in .env")
        return

    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": RECIPIENT_PHONE,
        "type": "text",
        "text": {"body": "🔔 Hello from JIVA Backend! If you see this, your API credentials are correct."},
    }

    try:
        print(f"Sending message to {RECIPIENT_PHONE}...")
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            print("✅ SUCCESS! Message sent.")
            print("Response:", response.json())
        else:
            print(f"❌ FAILED. Status: {response.status_code}")
            print("Response:", response.text)
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_send_message()
