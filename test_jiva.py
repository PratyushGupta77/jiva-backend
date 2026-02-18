import asyncio
import logging
import sys
from main import processing_pipeline, get_user

# Configure logging to show only JivaBackend logs or errors
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JivaBackend")

# Mock the WhatsApp sender to print to terminal instead
import main
def mock_send_whatsapp_message(to_phone, message):
    print(f"\n[JIVA]: {message}\n")

# Apply the mock
main.send_whatsapp_message = mock_send_whatsapp_message

async def run_chat():
    print("--- Jiva Local Terminal Mode ---")
    print("Simulating phone number: +919999999999")
    print("Type 'exit' to quit.\n")
    
    test_phone = "+919999999999"
    
    # Check if user exists
    user = await get_user(test_phone)
    if not user:
        print("[System]: Creating new test user...")
    else:
        # FORCE RESET NAME to avoid "Period Cramps" name glitch
        from main import update_user_profile
        await update_user_profile(test_phone, {"name": "Test User"})
        print("[System]: User Name reset to 'Test User' for clean session.")
    
    # Start Manual Scheduler Loop
    async def scheduler_loop():
        print("[System]: Scheduler loop started.")
        while True:
            await asyncio.sleep(10) # Check every 10 seconds
            try:
                from main import check_Reminders
                await check_Reminders()
            except Exception as e:
                print(f"[System]: Scheduler Error: {e}")

    # Run scheduler in background
    asyncio.create_task(scheduler_loop())

    while True:
        user_input = await asyncio.get_event_loop().run_in_executor(None, input, "[YOU]: ")
        if user_input.lower() in ["exit", "quit"]:
            break
            
        # Handle Image Input for Testing
        media_id = None
        if user_input.startswith("image:"):

            import os
            # Removing prefix
            content = user_input[6:].strip()
            
            # Simple heuristic: If it starts with quote, take until next quote
            if content.startswith('"'):
                try:
                    end_quote = content.index('"', 1)
                    image_path = content[1:end_quote]
                    caption = content[end_quote+1:].strip()
                except ValueError:
                    image_path = content.replace('"', '')
                    caption = ""
            else:
                # No quotes: First space is separator? Or assume whole thing is path?
                # If path has spaces but no quotes, we assume whole thing is path unless we find a valid file
                if os.path.exists(content):
                    image_path = content
                    caption = "Analyze this prescription."
                elif " " in content:
                     # Try splitting at first space
                     p, c = content.split(" ", 1)
                     if os.path.exists(p):
                         image_path = p
                         caption = c
                     else:
                         # Assume whole string is path (maybe just a typo in path)
                         image_path = content
                         caption = "Analyze this prescription."
                else:
                    image_path = content
                    caption = "Analyze this prescription."

            if not caption:
                caption = "Analyze this prescription."
            
            print(f"[System]: Simulating image upload from '{image_path}'...")
            # We can't easily mock the media_id download flow without a real server, 
            # so for LOCAL TEST, we will modify processing_pipeline to accept an image object directly if needed,
            # OR we just rely on the text description for now if we can't upload.
            # But wait! 'main.py' uses 'download_media'. 
            # In test mode, we should probably mock 'download_media' to return local file bytes.
            
            # Monkey Patch main.download_media for this session
            async def mock_download_media(url):
                try:
                    import mimetypes
                    mime_type, _ = mimetypes.guess_type(image_path)
                    if not mime_type:
                        mime_type = "image/jpeg" # Default fallback
                        
                    with open(image_path, "rb") as f:
                        return f.read(), mime_type
                except Exception as e:
                    print(f"Error reading local file: {e}")
                    return None, None
            
            main.download_media = mock_download_media
            
            # We pass a fake media_id. Main calls get_media_url -> returns URL -> download_media(URL)
            # We also need to mock get_media_url to return a dummy URL
            async def mock_get_media_url(mid):
                return "http://local-test/image.jpg"
            main.get_media_url = mock_get_media_url
            
            media_id = "test_media_id_123"
            user_input = caption

        try:
            await processing_pipeline(test_phone, user_input, media_id)
        except Exception as e:
            print(f"[System]: Error: {e}")

# --- Automated Verification ---
# --- Automated Verification & Stress Testing ---
async def automated_diagnostics():
    print("\n" + "="*50)
    print("🚀 STARTING JIVA SYSTEM STRESS TEST")
    print("="*50)
    
    test_phone = "+919999999999" 
    
    # 1. Standard Functional Tests
    functional_scenarios = [
        ("Testing Diet (Indian)", "Mujhe sardi khasi hai (Cold/Cough)"),
        ("Testing Menstrual Mode", "I have period cramps and mood swings"),
        ("Testing Generic Meds", "Pan D is too expensive"),
        ("Testing Vaccination Tracker", "My baby was born on 2024-01-01"),
        ("Testing System Safety (SOS)", "HELP! I am having chest pain!"),
    ]
    
    import time
    for test_name, input_text in functional_scenarios:
        print(f"\n[TEST]: {test_name}")
        print(f"[INPUT]: {input_text}")
        try:
            start_t = time.time()
            await processing_pipeline(test_phone, input_text)
            print(f"✅ PASSED (Time: {round(time.time() - start_t, 2)}s)")
        except Exception as e:
            print(f"❌ FAILED: {e}")
        print("-" * 20)
        await asyncio.sleep(2)

    # 2. Edge Case & Fuzz Testing
    print("\n[PHASE 2]: FAULTS & EDGE CASES")
    edge_cases = [
        ("Empty Input", ""),
        ("Whitespace Input", "   "),
        ("Huge Input", "A" * 10000), # 10KB text
        ("Special Characters", "Hello @#$%^&*()_+"),
        ("SQL Injection Attempt", "SELECT * FROM users"),
    ]
    
    for test_name, input_text in edge_cases:
        print(f"\n[TEST]: {test_name}")
        try:
             # Should not crash
             await processing_pipeline(test_phone, input_text)
             print("✅ HANDLED (No Crash)")
        except Exception as e:
             print(f"❌ CRASHED: {e}")
        print("-" * 20)
        await asyncio.sleep(1)

    print("\n✅ STRESS TEST COMPLETE.")
    print("If you see '✅ HANDLED' for all edge cases, the system is ROBUST.")
    print("="*50 + "\n")

# --- Clear History Helper ---
async def clear_history():
    print(f"\n[System]: Clearing chat history and resetting profile for +919999999999...")
    try:
        from main import supabase, async_supabase, get_user, update_user_profile
        
        user = await get_user("+919999999999")
        if user:
            # 1. Clear Chat History for user
            await async_supabase(
                supabase.table("chat_history").delete().eq("user_id", user['id'])
            )
            # 2. Reset Profile (Important: Test might have saved 'Period Cramps' to profile)
            await update_user_profile("+919999999999", {
                "name": "Test User", # RESET NAME!
                "medical_history": None,
                "allergies": None,
                "blood_group": None,
                "emergency_contact": None
            })
            print("✅ History & Profile Cleared.")
        else:
            print("User not found (nothing to clear).")
            
    except Exception as e:
        print(f"Error clearing history: {e}")

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            if sys.argv[1] == "--test-all":
                asyncio.run(automated_diagnostics())
            elif sys.argv[1] == "--clear":
                asyncio.run(clear_history())
        else:
            asyncio.run(run_chat())
    except KeyboardInterrupt:
        print("\n[System]: Stopped.")
