# How to Get a Permanent WhatsApp Token (Do This Once)

> [!IMPORTANT]
> The "Temporary Token" from the Developer Portal expires every **24 hours**.
> A **System User Token** never expires. Do this once and forget it.

## Steps

### Step 1: Open Meta Business Settings
Go to: https://business.facebook.com/settings/system-users?business_id=1698243904688210

### Step 2: Create a System User
1. Click **"Add"**
2. Name: `JivaBot`
3. Role: `Admin`
4. Click **"Create System User"**

### Step 3: Assign Your App
1. Click on `JivaBot` in the list
2. Click **"Add Assets"** (or "Assign Assets")
3. Select **Apps** → Select `Jiva` (your app)
4. Toggle **Full Control** → Click **Save Changes**

### Step 4: Generate the Token
1. Click **"Generate New Token"**
2. Select App: `Jiva`
3. Select Permissions:
   - ✅ `whatsapp_business_messaging`
   - ✅ `whatsapp_business_management`
4. Click **Generate Token**
5. **COPY THE TOKEN IMMEDIATELY** (it won't show again)

### Step 5: Update .env
Open `.env` and replace `WHATSAPP_ACCESS_TOKEN`:
```
WHATSAPP_ACCESS_TOKEN=<paste your new permanent token here>
```

### Done! ✅
This token never expires. You will never need to update it again.
