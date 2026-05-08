import csv
import os
import asyncio
from telethon import TelegramClient, events, Button
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.errors import PeerFloodError, UserPrivacyRestrictedError, FloodWaitError

# --- CONFIGURATION ---
API_ID = 38965322
API_HASH = '1aa65d34af642cd0cd761188ce071fc1'
BOT_TOKEN = '8617872114:AAG8EpQIK1s8BKPZHfZpevTNwJZpIvPF6j0'
PHONE = '+855968538178' 

# Initialize Clients
bot = TelegramClient('bot_session', API_ID, API_HASH)
user_client = TelegramClient('user_session', API_ID, API_HASH)

# State Management
SCRAPED_FILE = 'members.csv'
current_status = {"is_adding": False}

async def ensure_user_connected():
    if not user_client.is_connected():
        await user_client.connect()
    return await user_client.is_user_authorized()

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    buttons = [
        [Button.inline("🔍 Scrape Members", b"scrape")],
        [Button.inline("➕ Add Members", b"add")],
        [Button.inline("📊 Check Status", b"status")]
    ]
    await event.respond(
        "👋 **Telegram Scraper & Adder Bot**\n\n"
        "1. Please login via Terminal (PowerShell) first\n"
        "2. Click Scrape to get member list\n"
        "3. Click Add to invite members to your group", 
        buttons=buttons
    )

@bot.on(events.CallbackQuery(data=b"scrape"))
async def scrape_callback(event):
    if not await ensure_user_connected():
        await event.answer("❌ Account not connected! Please check your terminal.", alert=True)
        return
    await event.respond("🔄 Fetching Group list... please wait")
    try:
        result = await user_client(GetDialogsRequest(
            offset_date=None, offset_id=0, offset_peer=InputPeerEmpty(), limit=200, hash=0
        ))
        groups = [c for c in result.chats if getattr(c, 'megagroup', False)]
        buttons = [[Button.inline(f"📁 {g.title}", f"sg_{g.id}")] for g in groups[:15]]
        await event.respond("🎯 **Select source group to scrape from:**", buttons=buttons)
    except Exception as e:
        await event.respond(f"Error: {str(e)}")

@bot.on(events.CallbackQuery(data=lambda d: d.startswith(b"sg_")))
async def perform_scrape(event):
    group_id = int(event.data.decode().split('_')[1])
    await event.respond("⏳ Scraping members...")
    try:
        participants = await user_client.get_participants(group_id, aggressive=True)
        count = 0
        with open(SCRAPED_FILE, "w", encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'access_hash', 'username', 'name'])
            for u in participants:
                if not u.bot and u.username:
                    name = f"{u.first_name or ''} {u.last_name or ''}".strip()
                    writer.writerow([u.id, u.access_hash, u.username, name])
                    count += 1
        
        # Success message
        await event.respond(f"✅ Scraping successful! `{count}` members saved.")
        
        # Send CSV file to user for download
        await bot.send_file(
            event.chat_id, 
            SCRAPED_FILE, 
            caption=f"📊 Member list from Group ID: `{group_id}`"
        )
        
    except Exception as e:
        await event.respond(f"❌ Scraping failed: {str(e)}")

@bot.on(events.CallbackQuery(data=b"add"))
async def add_callback(event):
    if not os.path.exists(SCRAPED_FILE):
        await event.answer("❌ Please Scrape Members first!", alert=True)
        return
    if not await ensure_user_connected():
        await event.answer("❌ Terminal login required!", alert=True)
        return
    await event.respond("🔄 Fetching target groups...")
    try:
        result = await user_client(GetDialogsRequest(
            offset_date=None, offset_id=0, offset_peer=InputPeerEmpty(), limit=200, hash=0
        ))
        groups = [c for c in result.chats if getattr(c, 'megagroup', False)]
        buttons = [[Button.inline(f"📥 {g.title}", f"target_{g.id}")] for g in groups[:15]]
        await event.respond("🎯 **Select target group to add members to:**", buttons=buttons)
    except Exception as e:
        await event.respond(f"Error: {str(e)}")

@bot.on(events.CallbackQuery(data=lambda d: d.startswith(b"target_")))
async def perform_add(event):
    if current_status["is_adding"]:
        await event.answer("Adding process is already running!", alert=True)
        return
    target_group_id = int(event.data.decode().split('_')[1])
    current_status["is_adding"] = True
    users = []
    with open(SCRAPED_FILE, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        users = list(reader)
    
    await event.respond(f"🚀 Starting to add {len(users)} users (60s delay per user for safety)...")
    added = 0
    for user in users:
        try:
            await user_client(InviteToChannelRequest(target_group_id, [user['username']]))
            added += 1
            if added % 5 == 0: await event.respond(f"📈 Added: `{added}` members...")
            await asyncio.sleep(60) # Keep 60s to prevent ban
        except FloodWaitError as e:
            await event.respond(f"🛑 Blocked by Telegram for {e.seconds} seconds. Stopping process.")
            break
        except PeerFloodError:
            await event.respond("❌ Account limited (Flood Error). Stop using for 24h.")
            break
        except UserPrivacyRestrictedError:
            continue # Skip users with privacy settings
        except Exception:
            continue
            
    current_status["is_adding"] = False
    await event.respond(f"🏁 Task finished! Total added: `{added}`")

@bot.on(events.CallbackQuery(data=b"status"))
async def status_check(event):
    status = "Running 🟢" if current_status["is_adding"] else "Idle ⚪"
    await event.respond(f"📊 **Status**: {status}\nMember File: {'Available ✅' if os.path.exists(SCRAPED_FILE) else 'Missing ❌'}")

async def main():
    print("="*30)
    print("STEP 1: LOGIN TERMINAL")
    print("="*30)
    await user_client.start(phone=PHONE)
    print("\nSTEP 2: BOT STARTING")
    await bot.start(bot_token=BOT_TOKEN)
    print("READY! Go to Telegram and type /start")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass