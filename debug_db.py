import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime

# Load env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print(f"URL: {SUPABASE_URL}")
print(f"KEY: {SUPABASE_KEY[:10]}..." if SUPABASE_KEY else "KEY: None")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing Supabase credentials")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def test_db():
    print("--- Starting DB Test ---")
    
    # 1. Test User
    test_phone = "919999999999"
    print(f"\n1. Checking User {test_phone}...")
    
    try:
        user_response = supabase.table("users").select("*").eq("phone_number", test_phone).execute()
        user = None
        if user_response.data:
            user = user_response.data[0]
            print(f"✅ User found: {user['id']} - {user['name']}")
        else:
            print("⚠️ User not found. Creating...")
            create_response = supabase.table("users").insert({
                "phone_number": test_phone, 
                "name": "Test User"
            }).execute()
            if create_response.data:
                user = create_response.data[0]
                print(f"✅ User created: {user['id']}")
            else:
                print("❌ Failed to create user")
                return

        if not user:
            print("❌ No user to proceed")
            return

        user_id = user['id']

        # 2. Test Save Message
        print(f"\n2. Saving Message for {user_id}...")
        try:
            msg_response = supabase.table("chat_history").insert({
                "user_id": user_id,
                "role": "user",
                "content": "Test message from debug script"
            }).execute()
            print(f"✅ Message saved: {msg_response.data}")
        except Exception as e:
            print(f"❌ Error saving message: {e}")

        # 3. Test Fetch History
        print(f"\n3. Fetching History for {user_id}...")
        try:
            hist_response = supabase.table("chat_history").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(5).execute()
            if hist_response.data:
                print(f"✅ History found ({len(hist_response.data)} items):")
                for msg in hist_response.data:
                    print(f" - [{msg['role']}]: {msg['content']}")
            else:
                print("❌ History is EMPTY despite saving!")
                
        except Exception as e:
            print(f"❌ Error fetching history: {e}")

    except Exception as e:
        print(f"❌ General Error: {e}")

if __name__ == "__main__":
    # Fix for Windows asyncio loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_db())
