import os
import logging
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from supabase import create_client, Client
import google.generativeai as genai
from groq import Groq
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import requests
from dotenv import load_dotenv
from PIL import Image
import io
import time

# Load environment variables
load_dotenv()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("JivaBackend")

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

if not all([SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY, WHATSAPP_TOKEN, WHATSAPP_PHONE_ID]):
    logger.warning("Missing some environment variables. Ensure .env is set correctly.")

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Gemini (Primary AI)
genai.configure(api_key=GEMINI_API_KEY)

# Initialize Groq (Fallback AI)
groq_client = None
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
    logger.info("✅ Groq fallback enabled")
else:
    logger.warning("⚠️ GROQ_API_KEY not found. Fallback disabled.")

# Initialize FastAPI
app = FastAPI(title="Jiva - AI Health Guardian")

# Initialize Scheduler
scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

# --- Database Models & Helpers ---

class User(BaseModel):
    phone_number: str
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    medical_history: Optional[str] = None
    emergency_contact: Optional[str] = None

# Helper to run blocking calling in thread pool
async def async_supabase(query):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, query.execute)

async def get_user(phone_number: str) -> Optional[Dict[str, Any]]:
    try:
        response = await async_supabase(
            supabase.table("users").select("*").eq("phone_number", phone_number)
        )
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        return None

async def create_user(phone_number: str, name: str):
    try:
        await async_supabase(
            supabase.table("users").insert({"phone_number": phone_number, "name": name})
        )
    except Exception as e:
        logger.error(f"Error creating user: {e}")

async def update_user_profile(phone_number: str, updates: Dict[str, Any]):
     try:
        await async_supabase(
            supabase.table("users").update(updates).eq("phone_number", phone_number)
        )
     except Exception as e:
        logger.error(f"Error updating user profile: {e}")

async def get_chat_history(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    try:
        response = await async_supabase(
            supabase.table("chat_history")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .limit(limit)
        )
        return response.data[::-1] if response.data else [] # Return in chronological order
    except Exception as e:
        logger.error(f"Error fetching chat history: {e}")
        return []

async def save_message(user_id: str, role: str, content: str):
    try:
        await async_supabase(
            supabase.table("chat_history").insert({
                "user_id": user_id,
                "role": role,
                "content": content
            })
        )
    except Exception as e:
        logger.error(f"Error saving message: {e}")

async def create_reminder(user_id: str, reminder_time: datetime, message: str):
    try:
        await async_supabase(
            supabase.table("reminders").insert({
                "user_id": user_id,
                "reminder_time": reminder_time.isoformat(),
                "message": message,
                "status": "pending"
            })
        )
    except Exception as e:
        logger.error(f"Error creating reminder: {e}")

# --- WhatsApp Integration ---

def validate_whatsapp_token():
    """Validates the WhatsApp token on startup. Logs a clear error if expired."""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        logger.critical("❌ WHATSAPP_ACCESS_TOKEN or WHATSAPP_PHONE_NUMBER_ID is missing from .env!")
        return False
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            logger.info("✅ WhatsApp Token is VALID and active.")
            return True
        elif response.status_code == 401:
            logger.critical(
                "🚨 WHATSAPP TOKEN EXPIRED or INVALID! "
                "Go to Meta Dashboard → Generate a new System User Token → Update .env. "
                "Bot will NOT be able to send messages until fixed."
            )
            return False
        else:
            logger.warning(f"⚠️ WhatsApp token check returned status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Could not validate WhatsApp token: {e}")
        return False

def send_whatsapp_message(to_phone: str, message: str) -> bool:
    """Sends a WhatsApp message. Returns True on success, False on failure."""
    url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message},
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            logger.info(f"✅ WhatsApp message sent to {to_phone}")
            return True
        elif response.status_code == 401:
            logger.critical(
                "🚨 WHATSAPP TOKEN EXPIRED! Message NOT sent. "
                "Update WHATSAPP_ACCESS_TOKEN in .env with a permanent System User Token."
            )
            return False
        else:
            logger.error(f"❌ WhatsApp API error {response.status_code}: {response.text}")
            return False
    except requests.exceptions.Timeout:
        logger.error("❌ WhatsApp API timed out. Will retry next time.")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Failed to send WhatsApp message: {e}")
        return False

async def get_media_url(media_id: str) -> Optional[str]:
    url = f"https://graph.facebook.com/v18.0/{media_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 401:
            logger.critical("🚨 TOKEN EXPIRED while fetching media URL.")
            return None
        response.raise_for_status()
        return response.json().get("url")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get media URL: {e}")
        return None

async def download_media(media_url: str) -> Tuple[Optional[bytes], Optional[str]]:
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    try:
        response = requests.get(media_url, headers=headers, timeout=30)
        if response.status_code == 401:
            logger.critical("🚨 TOKEN EXPIRED while downloading media.")
            return None, None
        response.raise_for_status()
        return response.content, response.headers.get("Content-Type")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download media: {e}")
        return None, None

# --- AI Logic ---

async def processing_pipeline(user_phone: str, message_body: str, media_id: str = None):
    # 1. Check User Existence
    user = await get_user(user_phone)
    
    if not user:
        await create_user(user_phone, "Pending")
        # First-time greeting
        send_whatsapp_message(user_phone, "Jai Shree Shyam! Namaste! I am Jiva, your personal Health Guardian. Before we start, may I know your good name?")
        return 

    if user.get("name") == "Pending":
        # This message is likely the name.
        new_name = message_body.strip()
        # Update user
        try:
             await update_user_profile(user_phone, {"name": new_name})
             send_whatsapp_message(user_phone, f"Namaste {new_name}! I am ready to help you with your health. How are you feeling today?")
        except Exception as e:
            logger.error(f"Failed to update name: {e}")
            send_whatsapp_message(user_phone, "I had trouble saving your name. But let's continue. How can I help?")
        return

    # Normal Flow
    user_id = user['id']
    user_name = user.get('name', 'Friend')
    
    # Construct User Profile String
    profile_str = f"Name: {user_name}\n"
    if user.get('age'): profile_str += f"Age: {user['age']}\n"
    if user.get('gender'): profile_str += f"Gender: {user['gender']}\n"
    if user.get('allergies'): profile_str += f"Allergies: {user['allergies']}\n"
    if user.get('medical_history'): profile_str += f"History: {user['medical_history']}\n"
    if user.get('emergency_contact'): profile_str += f"Emergency Contact: {user['emergency_contact']}\n"

    # 2. Fetch Context
    chat_history = await get_chat_history(user_id)
    
    # 3. Media Handling (Vision & Voice)
    media_part = None
    media_type_label = "Image"
    
    if media_id:
        media_url = await get_media_url(media_id)
        if media_url:
            media_data, mime_type = await download_media(media_url)
            if media_data:
                if mime_type and mime_type.startswith("image"):
                    image = Image.open(io.BytesIO(media_data))
                    media_part = image
                    media_type_label = "Image"
                    message_body += "\n[System: User uploaded an medical image/prescription]"
                elif mime_type and mime_type.startswith("audio"):
                    media_part = {"mime_type": mime_type, "data": media_data}
                    media_type_label = "Audio"
                    message_body += "\n[System: User sent a Voice Note. Listen carefully and reply.]"
                else:
                    logger.warning(f"Unsupported media type: {mime_type}")

    # 4. Construct Prompt
    current_time = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    
    # Determine greeting based on context
    hour = datetime.now().hour
    # Only force intro if strictly no history AND user name suggests newness, or just rely on time
    is_first_message = len(chat_history) == 0
    
    if is_first_message:
         # Robust Greeting Logic:
         # If the user asks a question (e.g., "I have a headache"), answer directly.
         # Only introduce yourself if the user just said "Hi" or "Hello".
         # This prevents repetitive intros if chat history fails or races.
         greeting_guide = f"Context: No chat history found. If user asks a specific question, ANSWER DIRECTLY (do not introduce yourself). If user says 'Hi'/'Hello', say: 'Namaste {user_name}! Main Jiva hoon.'"
    elif 6 <= hour < 12:
        greeting_guide = f"Use morning greeting: 'Good morning {user_name}! Kaisi tabiyat hai aaj?'"
    elif 12 <= hour < 17:
        greeting_guide = f"Use afternoon greeting: 'Hello {user_name}! Kya haal hai?'"
    elif 17 <= hour < 21:
        greeting_guide = f"Use evening greeting: 'Namaste {user_name}! Sab theek?'"
    else:
        greeting_guide = f"Use night greeting: 'Hi {user_name}! Abhi tak jaage?'"
    
    system_instruction = f"""
You are **Jiva - An Advanced AI Health Assistant**.

🎯 **YOUR MISSION**:
Provide **professional, medically-grounded, and actionable** health guidance. You are NOT a replacement for a doctor, but you are a **highly intelligent medical triage assistant**.

🚫 **CRITICAL RULES (STRICT COMPLIANCE REQUIRED)**:
1. **NO REPETITIVE GREETINGS**: Do NOT say "Namaste", "Hello", or introduce yourself in every message. Only greet IF the user explicitly greets you first (e.g., "Hi Jiva"). Otherwise, **ANSWER DIRECTLY**.
2. **NO GENERIC "CHAI/DOLO" ADVICE**: Do not suggest medicines unless you have analyzed the symptoms. "Drink tea" is not a medical solution for everything.
3. **EMERGENCY FIRST**: If symptoms suggest a crisis (Heart attack, Stroke, Severe Bleeding, Breathing difficulty), **STOP EVERYTHING** and trigger the Emergency Protocol immediately.

🧬 **MEDICAL TRIAGE PROTOCOL (follow this flow)**:

**PHASE 1: ASSESSMENT (The "Doctor's Mind")**
- Don't just accept "Headache". Ask: *Location? Type (throbbing/dull)? Duration? Associated symptoms (nausea, vision obs)?*
- Max 2-3 sharp, clinical questions to narrow down the cause.

**PHASE 2: DIFFERENTIAL ANALYSIS**
- Based on answers, think: "Could this turn into a migraine? Or is it just stress?"
- Explain your reasoning briefly to the user.

**PHASE 3: MANAGEMENT PLAN**
- **Primary**: Immediate relief measures (Positioning, Breathing, Hydration).
- **Secondary**: Safe OTC medications (Paracetamol 650mg, ORS, Antacids) - *Always mention dosage warnings*.
- **Tertiary**: Home/Natural remedies (only if clinically supported, e.g., Steam key for congestion).

⏰ **CURRENT CONTEXT**:
Time: {current_time}
User Context: {profile_str}
Greeting Guidance: "{greeting_guide}" (Use this ONLY if conversation just started. Otherwise IGNORE.)

🚨 **EMERGENCY RESPONSE FORMAT (When specific keywords detected: Chest pain, breathless, collapsed)**:
"🚨 **CRITICAL MEDICAL ALERT**
• **IMMEDIATE ACTION**: [Specific life-saving step, e.g., 'Sit down, chew Aspirin 300mg']
• **CALL EMERGENCY**: Dial **108** or **102** NOW.
• **HOSPITAL**: Go to the nearest ER immediately.
[[SOS]]" 
(The [[SOS]] tag triggers an alert to their family. USE IT for serious threats.)

💊 **PRESCRIPTION & REPORT ANALYSIS**:
If an image is provided:
1. **Identify**: Is it a Prescription? Lab Report? Medicine Strip?
2. **Extract**: Doctor's Name, Patient Name, Medicines (Name + Dosage + Frequency).
3. **Action**: Explain what the medicine is for. 
4. **Scheduling**: Create reminders using the tag [[SCHEDULE_REMINDERS: [{{"message": "Take Metformin", "time": "2023-10-27T09:00:00"}}]]]

🗣️ **TONE & STYLE**:
- **Professional & Assuring**: Like a senior resident doctor.
- **Direct**: Get to the point. No fluff.
- **Structured**: Use Bullet points.
- **Indian Context**: Understand Indian brand names (Crocin, Dolo, Pan D, Azithral) and diet.

**EXAMPLE (Good Response)**:
User: "I have a severe headache on one side."
Jiva: "Is there any nausea or sensitivity to light? How long has it been hurting?
It sounds like it could be a **Migraine**.
• **Immediate**: Go to a dark, quiet room. Rest.
• **Meds**: You can take a Paracetamol (Dolo 650) if you have no allergies. If it persists > 24hrs, see a doctor.
• **Hydrate**: Drink water slowly."

**EXAMPLE (Bad Response)**:
User: "Headache."
Jiva: "Namaste! Have some chai and take rest. Everything will be fine." (❌ TOO SIMPLE)
"""

    history_content = []
    for msg in chat_history:
        role = "user" if msg['role'] == "user" else "model"
        history_content.append({"role": role, "parts": [msg['content']]})

    # --- MULTI-MODEL FALLBACK SYSTEM (validated by fix_jiva.py) ---
    # Status: 1.5-Flash returns 404 (Broken). 2.0-Flash returns 429 (Valid but Busy).
    # Strategy: Use 2.0 models ONLY and WAIT on rate limits.
    
    print("--------------------------------------------------")
    print("--- 🚀 RELOADING JIVA BRAINS (VERSION: 2.0-ONLY) ---")
    print("--------------------------------------------------")

    models_to_try = [
        "gemini-2.0-flash",         # Verified Exists (returns 429)
        "gemini-2.0-flash-lite-001" # Verified Exists (returns 429)
    ]
    
    response_text = ""
    success = False
    
    import time
    
    for model_name in models_to_try:
        try:
            # Configure Model dynamically
            current_model = genai.GenerativeModel(model_name)
            
            if media_part:
                # Media Generation (One-shot)
                response = current_model.generate_content([system_instruction, f"User's {media_type_label}:", media_part, "User's Query:", message_body])
                response_text = response.text
                success = True
                logger.info(f"✅ Success with {model_name}")
                break
            else:
                # Text Chat (History aware)
                start_time = time.time()
                chat_session = current_model.start_chat(history=history_content)
                prompt = f"{system_instruction}\n\nUser: {message_body}"
                
                response = chat_session.send_message(prompt)
                response_text = response.text
                success = True
                logger.info(f"✅ Success with {model_name} (took {round(time.time() - start_time, 2)}s)")
                break
                
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
                logger.warning(f"⚠️ Rate Limit on {model_name}. Switching to next model immediately...")
                # EMERGENCY OPTIMIZATION: Skip wait, switch to Groq immediately for patient safety
                continue 
            else:
                # Genuine error (like safety filter or network)
                if "500" in error_str or "503" in error_str:
                     logger.warning(f"⚠️ Server Error on {model_name}. Switching...")
                     continue
                
                logger.error(f"❌ Critical Error on {model_name}: {e}")
                continue


    # --- GROQ FALLBACK (If all Gemini models fail) ---
    if not success and groq_client:
        logger.warning("🔄 Gemini quota exhausted. Switching to GROQ fallback...")
        try:
            groq_response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": message_body}
                ],
                temperature=0.7,
                max_tokens=1024
            )
            response_text = groq_response.choices[0].message.content
            success = True
            logger.info("✅ Success with Groq fallback")
        except Exception as e:
            logger.error(f"❌ Groq fallback also failed: {e}")
    
    if not success:
        logger.error("ALL AI SYSTEMS FAILED (Gemini + Groq).")
        response_text = "⚠️ Server Overload: All AI systems are busy. Emergency? Call 108 immediately."
        final_reply = response_text
        import json
        
        # Helper to clean response
        def extract_json(tag, text):
            if tag in text:
                try:
                    s = text.find(tag)
                    e = text.find("]]", s)
                    json_str = text[s + len(tag) : e]
                    return json.loads(json_str), text[:s].strip()
                except Exception as e:
                    logger.error(f"JSON Error: {e}")
                    return None, text.replace(f"{tag} {json_str}]]", "").strip()
            return None, text

        # Check for Profile Update
        updates, final_reply = extract_json("[[UPDATE_PROFILE:", final_reply)
        if updates:
            await update_user_profile(user_phone, updates)
            if "emergency_contact" in updates:
                 final_reply += f"\n(✅ Saved Emergency Contact: {updates['emergency_contact']})"

        # Check for Batch Reminders
        reminder_list, final_reply = extract_json("[[SCHEDULE_REMINDERS:", final_reply)
        if reminder_list:
            try:
                for item in reminder_list:
                    r_time = datetime.fromisoformat(item['time'])
                    await create_reminder(user_id, r_time, item['message'])
                    logger.info(f"Reminder set for {r_time}")
            except Exception as e:
                logger.error(f"Reminder Batch Error: {e}")
        
        # Check for SOS
        if "[[SOS]]" in response_text:
            final_reply = final_reply.replace("[[SOS]]", "").strip()
            contact = user.get('emergency_contact')
            if contact:
                logger.warning(f"SOS Triggered for user {user_phone}")
                send_whatsapp_message(contact, f"🚨 EMERGENCY: {user_name} ({user_phone}) needs help! Message: '{message_body}'")
                final_reply += "\n\n🚨 **I HAVE ALERTED YOUR EMERGENCY CONTACT.** Help is on the way."
            else:
                 final_reply += "\n\n⚠️ **I tried to alert your family, but NO Emergency Contact is saved!** Please call 102/108 immediately."

        # 6. Save interactions
        await save_message(user_id, "user", message_body) 
        await save_message(user_id, "assistant", final_reply)
        
        # 7. Send Response
        send_whatsapp_message(user_phone, final_reply)
    else:
        # Send fallback message directly
        send_whatsapp_message(user_phone, response_text)

async def handle_incoming_message(payload: Dict[str, Any]):
    try:
        entry = payload['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        
        if 'messages' in value:
            message = value['messages'][0]
            from_phone = message['from']
            msg_type = message['type']
            
            media_id = None
            body = ""
            
            if msg_type == 'text':
                body = message['text']['body']
            elif msg_type == 'image':
                media_id = message['image']['id']
                body = message['image'].get('caption', "")
            elif msg_type == 'audio':
                media_id = message['audio']['id']
                body = "" # Audio messages don't have captions
            else:
                return

            await processing_pipeline(from_phone, body, media_id)
            
    except Exception as e:
        logger.error(f"Error processing webhook payload: {e}")

# --- Endpoints ---

@app.get("/")
async def root():
    return {"status": "Jiva is active"}

@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("Webhook Verified.")
            return int(challenge)
        else:
            raise HTTPException(status_code=403, detail="Verification failed")
    return JSONResponse(content={"error": "Missing parameters"}, status_code=400)

@app.post("/webhook")
async def webhook_handler(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    background_tasks.add_task(handle_incoming_message, payload)
    return {"status": "received"}

# --- Scheduler ---

async def check_Reminders():
    try:
        now = datetime.now()
        # Get pending reminders
        response = await async_supabase(
            supabase.table("reminders")
            .select("*")
            .eq("status", "pending")
            .lte("reminder_time", now.isoformat())
        )
        
        reminders = response.data
        
        if reminders:
            logger.info(f"Found {len(reminders)} pending reminders")
            for reminder in reminders:
                try:
                    # Get user phone number
                    user_response = await async_supabase(
                        supabase.table("users").select("phone_number").eq("id", reminder['user_id']).single()
                    )
                    
                    if user_response.data:
                        phone = user_response.data['phone_number']
                        message = f"⏰ Reminder: {reminder['message']}"
                        send_whatsapp_message(phone, message)
                        
                        # Mark as sent
                        await async_supabase(
                            supabase.table("reminders").update({"status": "sent"}).eq("id", reminder['id'])
                        )
                        logger.info(f"✅ Sent reminder {reminder['id']} to {phone}")
                    else:
                        logger.warning(f"User not found for reminder {reminder['id']}")
                except Exception as e:
                    logger.error(f"Failed to send reminder {reminder['id']}: {e}")
                
    except Exception as e:
        logger.error(f"Scheduler Error: {e}")

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Jiva AI Health Assistant"}

@app.on_event("startup")
async def startup_event():
    scheduler.add_job(check_Reminders, IntervalTrigger(seconds=60))
    scheduler.start()
    logger.info("Scheduler started.")
    # Validate WhatsApp token on startup - fail fast so you know immediately
    validate_whatsapp_token()

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    logger.info("Scheduler shutdown.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)