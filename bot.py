import os
import sys
import importlib
import asyncio

# --- REQUIREMENT CHECKER START ---
REQUIRED_MODULES = {
    "telebot": "pyTelegramBotAPI",
    "requests": "requests",
    "urllib3": "urllib3",
    "dotenv": "python-dotenv",
    "ddddocr": "ddddocr",
    "fitz": "pymupdf",
    "phonenumbers": "phonenumbers"
}

REQUIRED_FILES = {
    "stats_manager.py": "Core stats registry manager",
    "aadhaar_engine.py": "Core Aadhaar backend engine",
    "retrive-eid.py": "Phase 1 bypass subprocess",
    "aadhar-downlaod.py": "Phase 2 download subprocess",
    "pdf_processor.py": "PDF processing engine"
}

def check_startup_requirements():
    print("📋 ========================================================")
    print("        AADHAAR TELEGRAM BOT - STARTUP VERIFICATION        ")
    print("============================================================")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Check Python Package Modules
    print("\n📦 Verifying Python Package Dependencies:")
    print("------------------------------------------------------------")
    missing_packages = []
    for module_name, pip_name in REQUIRED_MODULES.items():
        try:
            importlib.import_module(module_name)
            print(f"  🟢 {pip_name:<20} -> PRESENT")
        except ImportError:
            print(f"  🔴 {pip_name:<20} -> MISSING")
            missing_packages.append(pip_name)
            

    # 3. Check Vital Files and Folders
    print("\n📂 Verifying Core Codebase Files:")
    print("------------------------------------------------------------")
    missing_files = []
    for file_name, desc in REQUIRED_FILES.items():
        full_path = os.path.join(base_dir, file_name)
        if os.path.exists(full_path):
            print(f"  🟢 {file_name:<22} -> PRESENT ({desc})")
        else:
            print(f"  🔴 {file_name:<22} -> MISSING ({desc})")
            missing_files.append(file_name)
            
    # 4. Check Environment Configuration
    print("\n🔑 Verifying Environment Settings (.env):")
    print("------------------------------------------------------------")
    env_path = os.path.join(base_dir, ".env")
    env_exists = os.path.exists(env_path)
    if env_exists:
        print("  🟢 .env Configuration File -> FOUND")
        with open(env_path, "r", encoding="utf-8") as f:
            env_content = f.read()
            
        token_found = False
        admin_found = False
        for line in env_content.splitlines():
            line = line.strip()
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                val = line.split("=", 1)[1].strip().replace("'", "").replace('"', '')
                if val:
                    token_found = True
            elif line.startswith("ADMIN_IDS="):
                val = line.split("=", 1)[1].strip().replace("'", "").replace('"', '')
                if val:
                    admin_found = True
                    
        if token_found:
            print("  🟢 TELEGRAM_BOT_TOKEN      -> CONFIGURED")
        else:
            print("  🔴 TELEGRAM_BOT_TOKEN      -> MISSING OR EMPTY")
            
        if admin_found:
            print("  🟢 ADMIN_IDS               -> CONFIGURED")
        else:
            print("  🟡 ADMIN_IDS               -> WARNING (Not set in .env)")
    else:
        print("  🔴 .env Configuration File -> MISSING")
        token_found = False
        admin_found = False
        
    print("============================================================\n")
    
    has_errors = (
        len(missing_packages) > 0 
        or len(missing_files) > 0 
        or not env_exists 
        or not token_found
    )
    
    if has_errors:
        print("❌ STARTUP ERROR: Critical requirements are missing!")
        print("👇 Please execute the following commands to resolve the errors:\n")
        
        if len(missing_packages) > 0:
            print("👉 1. Install missing Python dependencies:")
            print(f"   Command: pip install {' '.join(missing_packages)}\n")
            
        if len(missing_files) > 0:
            print("👉 2. Restore missing core codebase files:")
            for f in missing_files:
                print(f"   - {f} ({REQUIRED_FILES[f]})")
            print("   Please check your repository to restore these files.\n")
            
        if not env_exists or not token_found:
            print("👉 3. Configure environment settings:")
            print("   Create a '.env' file in the bot root folder containing:")
            print("   TELEGRAM_BOT_TOKEN=8705250266:AAFd7iFVF4LIL3AeCZu0Rhx98P3OS1ZkhAg")
            print("   ADMIN_IDS=ADMIN_ID_1,ADMIN_ID_2\n")
            
        print("============================================================")
        sys.exit(1)
    else:
        print("✨ All requirements are met! Starting Aadhaar Telegram Bot...\n")

# Run the checker before importing external dependencies
check_startup_requirements()
# --- REQUIREMENT CHECKER END ---

import telebot
import json
import threading
import time
from telebot import types, apihelper
from dotenv import load_dotenv

# Load environmental variables from .env file
load_dotenv()

# Force all spawned python subprocesses to use UTF-8 output encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Import updated engine
import aadhaar_engine
from aadhaar_engine import user_page_registry

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    print("❌ Error: TELEGRAM_BOT_TOKEN is not defined in the environment or .env file.")
    sys.exit(1)

DEVELOPER_USERNAME = os.getenv('DEVELOPER_USERNAME', '@ShadowCipherX1')

ADMIN_IDS_RAW = os.getenv('ADMIN_IDS')
if not ADMIN_IDS_RAW:
    print("⚠️ Warning: ADMIN_IDS is not configured in .env. Admin dashboard features will be unavailable.")
    ADMIN_IDS = []
else:
    ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(',') if x.strip().isdigit()]

REQUIRED_CHANNELS_RAW = os.getenv('REQUIRED_CHANNEL_IDS')
if not REQUIRED_CHANNELS_RAW:
    print("⚠️ Warning: REQUIRED_CHANNEL_IDS is not configured in .env. Channel check features will be bypassed.")
    REQUIRED_CHANNELS = []
else:
    REQUIRED_CHANNELS = []
    for x in REQUIRED_CHANNELS_RAW.split(','):
        x = x.strip()
        # Parse channel IDs which can be integers (e.g. -100xxx) or strings (e.g. @channelusername)
        if x:
            if x.startswith('-') and x[1:].isdigit():
                REQUIRED_CHANNELS.append(int(x))
            elif x.isdigit():
                REQUIRED_CHANNELS.append(int(x))
            else:
                REQUIRED_CHANNELS.append(x)

import stats_manager

# Custom Exception Handler to prevent worker thread crashes from bubbling to infinity_polling
class BotExceptionHandler(telebot.ExceptionHandler):
    def handle(self, exception):
        print(f"⚠️ [TELEBOT EXCEPTION] Handled seamlessly: {exception}")
        if "getaddrinfo failed" in str(exception) or "NewConnectionError" in str(exception) or "Max retries exceeded" in str(exception):
            time.sleep(5) # Prevent log spam if internet connection drops
        return True

# Prevent idle socket timeouts by refreshing the HTTP session periodically
apihelper.SESSION_TIME_TO_LIVE = 5 * 60

bot = telebot.TeleBot(TOKEN, parse_mode='HTML', exception_handler=BotExceptionHandler())

# Safe wrappers for sending and editing messages to auto-retry on ConnectionResetError
orig_send_message = bot.send_message
orig_edit_message_text = bot.edit_message_text

def safe_send_message(*args, **kwargs):
    kwargs.pop('timeout', None)
    for attempt in range(3):
        try:
            return orig_send_message(*args, **kwargs)
        except Exception as e:
            err_str = str(e)
            if "blocked by the user" in err_str or "Forbidden" in err_str or "chat not found" in err_str or "403" in err_str:
                print(f"🚫 [TELEGRAM SEND FORBIDDEN]: Bot is blocked by user or chat not found. Skipping retries.")
                raise e
            print(f"⚠️ [TELEGRAM SEND RETRY {attempt+1}/3]: {e}")
            if attempt == 2:
                raise e
            time.sleep(1)

def safe_edit_message_text(*args, **kwargs):
    kwargs.pop('timeout', None)
    for attempt in range(3):
        try:
            return orig_edit_message_text(*args, **kwargs)
        except Exception as e:
            err_str = str(e)
            if "message is not modified" in err_str:
                print("📝 [TELEGRAM EDIT]: Message is not modified. Suppressing error.")
                return True
            if "blocked by the user" in err_str or "Forbidden" in err_str or "chat not found" in err_str or "403" in err_str:
                print(f"🚫 [TELEGRAM EDIT FORBIDDEN]: Bot is blocked by user or chat not found. Skipping retries.")
                raise e
            print(f"⚠️ [TELEGRAM EDIT RETRY {attempt+1}/3]: {e}")
            if attempt == 2:
                raise e
            time.sleep(1)

bot.send_message = safe_send_message
bot.edit_message_text = safe_edit_message_text

orig_send_photo = bot.send_photo
orig_send_document = bot.send_document

def safe_send_photo(*args, **kwargs):
    kwargs.pop('timeout', None)
    for attempt in range(3):
        try:
            return orig_send_photo(*args, **kwargs)
        except Exception as e:
            print(f"⚠️ [TELEGRAM SEND PHOTO RETRY {attempt+1}/3]: {e}")
            if attempt == 2:
                raise e
            time.sleep(2)

def safe_send_document(*args, **kwargs):
    kwargs.pop('timeout', None)
    for attempt in range(3):
        try:
            return orig_send_document(*args, **kwargs)
        except Exception as e:
            print(f"⚠️ [TELEGRAM SEND DOCUMENT RETRY {attempt+1}/3]: {e}")
            if attempt == 2:
                raise e
            time.sleep(2)

bot.send_photo = safe_send_photo
bot.send_document = safe_send_document


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
user_states = {}
loop = None # Global loop reference

def check_user_joined(chat_id):
    """
    Checks if a user has joined all required channels listed in REQUIRED_CHANNELS.
    Bypasses if user is in ADMIN_IDS.
    Returns True if joined or bypassed, False otherwise.
    """
    if chat_id < 0:
        return True
    if chat_id in ADMIN_IDS:
        return True
    if not REQUIRED_CHANNELS:
        return True
        
    for channel in REQUIRED_CHANNELS:
        try:
            member = bot.get_chat_member(chat_id=channel, user_id=chat_id)
            if member.status in ['left', 'kicked']:
                return False
        except apihelper.ApiTelegramException as e:
            err_msg = str(e).lower()
            # If the error is because the user is not found or not a participant, they haven't joined
            if "user not found" in err_msg or "user_not_participant" in err_msg:
                return False
            # Otherwise it's a configuration issue (bot is not admin, chat not found), bypass
            print(f"⚠️ [JOIN CHECK] Configuration issue for channel {channel}: {e}")
        except Exception as e:
            # If bot cannot check (e.g. general exception), log it and bypass
            print(f"⚠️ [JOIN CHECK] Failed to check channel {channel} for user {chat_id}: {e}")
            
    return True

def prompt_join_channels(chat_id):
    """
    Sends a message to the user prompting them to join the required channels.
    """
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    join_text = "⚠️ <b>Join Required Channels</b>\n\nBot ko use karne ke liye aapko niche diye gaye channels ko join karna zaroori hai:\n"
    
    for idx, channel in enumerate(REQUIRED_CHANNELS, 1):
        url = None
        title = f"Channel {idx}"
        try:
            chat_info = bot.get_chat(channel)
            title = chat_info.title or f"Channel {idx}"
            
            if chat_info.username:
                url = f"https://t.me/{chat_info.username}"
            elif chat_info.invite_link:
                url = chat_info.invite_link
            else:
                try:
                    # Dynamically export chat invite link (requires admin invite rights)
                    url = bot.export_chat_invite_link(channel)
                except Exception as ex:
                    print(f"⚠️ [JOIN CHECK] Export invite link failed for {channel}: {ex}")
                    url = f"https://t.me/c/{str(channel).replace('-100', '')}"
        except Exception as e:
            print(f"⚠️ [JOIN CHECK] Error getting chat info for {channel}: {e}")
            url = f"https://t.me/ShadowCipherX1" # Fallback to developer
                
        btn = types.InlineKeyboardButton(f"📢 Join {title}", url=url)
        markup.add(btn)
            
    # Add a check button to re-verify join status
    btn_check = types.InlineKeyboardButton("🔄 Re-Verify / Start", callback_data="check_joined_status")
    markup.add(btn_check)
    
    bot.send_message(chat_id, join_text, reply_markup=markup, parse_mode='HTML')

def esc(s):
    return str(s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def get_ui_card(step_num, title, description, target=None, show_tip=True):
    body = ""
    if step_num:
        body += f"📱 <b>STEP {step_num}/4: {title}</b>\n\n"
    else:
        body += f"⭐ <b>{title}</b>\n\n"
        
    body += f"{description}\n"
    
    if target:
        body += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
        body += f"📱 <b>Target Mobile:</b> <code>{target}</code>\n"
            
    if show_tip:
        body += (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>Tip: Send <b>/cancel</b> to abort.</i>"
        )
    else:
        body += "━━━━━━━━━━━━━━━━━━━━━━"
        
    return body

def send_zero_credits_dashboard(chat_id, message_id=None):
    try:
        bot_username = bot.get_me().username
    except Exception as e:
        print(f"⚠️ Failed to get bot username: {e}")
        bot_username = "bot"
        
    referral_link = f"https://t.me/{bot_username}?start=ref_{chat_id}"
    
    data = stats_manager.load_stats()
    
    # Find user record in stats.json
    user_record = None
    for u in data.get("users", []):
        if isinstance(u, dict) and str(u.get("chat_id")) == str(chat_id):
            user_record = u
            break
            
    join_date = user_record.get("joined", "N/A") if user_record else "N/A"
    
    # Success count
    history = data.get("cracked_history", [])
    success_count = sum(1 for r in history if str(r.get("chat_id")) == str(chat_id))
    
    # Referred count
    referred_count = 0
    for u in data.get("users", []):
        if isinstance(u, dict):
            ref_by = u.get("referred_by")
            if ref_by is not None and str(ref_by) == str(chat_id):
                referred_count += 1
            
    zero_credits_text = (
        "⚠️ <b>NO CREDITS REMAINING!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Aapke paas Aadhaar Nikalne ke liye credits khatam ho gaye hain. "
        "Naye credits lene ke liye niche diye gaye methods use karein:\n\n"
        "👤 <b>YOUR PROFILE STATS:</b>\n"
        f"  ├─ <b>Telegram ID:</b> <code>{chat_id}</code>\n"
        f"  ├─ <b>Joined Date:</b> <code>{join_date}</code>\n"
        f"  ├─ <b>Credit Balance:</b> <code>0 💳</code>\n"
        f"  ├─ <b>Success Checked:</b> <code>{success_count} ✅</code>\n"
        f"  └─ <b>Total Referrals:</b> <code>{referred_count} joined</code>\n\n"
        "🤝 <b>REFER & EARN CREDITS:</b>\n"
        "Apne dosto ko bot par invite karein aur har successful join par <b>1 Credit</b> payein!\n\n"
        "🔗 <b>Your Invite Link:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💬 Admin/Developer se credits lene ke liye niche direct click karein."
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_buy = types.InlineKeyboardButton("👨‍💻 Contact Admin", url=f"https://t.me/{DEVELOPER_USERNAME}")
    btn_refresh = types.InlineKeyboardButton("🔄 Refresh Credits", callback_data="refresh_zero_credits")
    markup.add(btn_buy, btn_refresh)
    
    if message_id:
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=zero_credits_text, reply_markup=markup, parse_mode='HTML')
        except Exception as e:
            print(f"⚠️ [ZERO_CREDITS] Failed to edit welcome text: {e}")
            bot.send_message(chat_id, zero_credits_text, reply_markup=markup, parse_mode='HTML')
    else:
        bot.send_message(chat_id, zero_credits_text, reply_markup=markup, parse_mode='HTML')


def send_welcome_dashboard(chat_id, message_id=None):
    mode = stats_manager.get_bot_mode()
    
    credits_info = ""
    if mode == "paid":
        credits = stats_manager.get_user_credits(chat_id)
        credits_info = f"\n💳 <b>Credits Left:</b> <code>{credits}</code>\n"
    else:
        credits_info = f"\n💳 <b>Credits Left:</b> <code>Unlimited</code>\n"
        
    welcome_text = (
        "👋 <b>Welcome to the Aadhaar BOT!</b>\n"
        "Extract Aadhaar details and generate decrypted PDFs instantly.\n"
        f"{credits_info}\n"
        "⚡ <b>Select an option below to begin:</b>"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_dev = types.InlineKeyboardButton("👨‍💻 Developer", url=f"https://t.me/{@ShadowCipherX1}")
    btn_start = types.InlineKeyboardButton("🚀 Start", callback_data="start_bypass")
    markup.add(btn_dev, btn_start)
    
    if message_id:
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=welcome_text, reply_markup=markup, parse_mode='HTML')
        except Exception as e:
            print(f"⚠️ [WELCOME] Failed to edit welcome text: {e}")
            bot.send_message(chat_id, welcome_text, reply_markup=markup, parse_mode='HTML')
    else:
        bot.send_message(chat_id, welcome_text, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    
    # Handle referral rewards first
    parts = message.text.split()
    referrer_id = None
    if len(parts) > 1 and parts[1].startswith("ref_"):
        try:
            referrer_id = int(parts[1].split("_")[1])
        except:
            pass

    is_new_user = not stats_manager.is_user_registered(chat_id)
    
    try:
        stats_manager.register_visit(chat_id, username=message.from_user.username, first_name=message.from_user.first_name)
    except Exception as e:
        print(f"⚠️ [STATS] Failed to register visit: {e}")
        
    if is_new_user and referrer_id and referrer_id != chat_id:
        try:
            stats_manager.add_user_credits(referrer_id, 1)
            # Save referral relationship in the new user's profile
            data = stats_manager.load_stats()
            for u in data.get("users", []):
                if isinstance(u, dict) and u.get("chat_id") == chat_id:
                    u["referred_by"] = referrer_id
                    break
            stats_manager.save_stats(data)
            
            # Send notification to the referrer
            new_user_name = message.from_user.first_name or "Someone"
            ref_notify = f"User named {new_user_name} joined through your link and you got 1 credit"
            bot.send_message(referrer_id, ref_notify)
        except Exception as ref_err:
            print(f"⚠️ [REFERRAL] Error rewarding referrer {referrer_id}: {ref_err}")
        
    # Check Channel Join Status
    if not check_user_joined(chat_id):
        prompt_join_channels(chat_id)
        return

    str_chat_id = str(chat_id)
    if str_chat_id in aadhaar_engine.active_tasks or user_states.get(chat_id, {}).get('step') in ['PROCESSING', 'FETCHING_INFO']:
        warn_msg = (
            "⚠️ <b>Active Session Running</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⏳ Aapka ek active task pehle se chal raha hai.\n"
            "Kripya is task ke complete hone ka wait karein ya naya process shuru karne ke liye <code>/cancel</code> send karein."
        )
        bot.send_message(chat_id, warn_msg, parse_mode='HTML')
        return
        
    user_states[chat_id] = {'step': 'IDLE'}
    send_welcome_dashboard(chat_id)


@bot.callback_query_handler(func=lambda call: call.data == 'start_bypass')
def handle_start_bypass(call):
    chat_id = call.message.chat.id
    print(f"📥 [CALLBACK] start_bypass triggered for chat_id: {chat_id}")

    # Answer the callback query immediately to dismiss the Telegram button spinner
    try:
        bot.answer_callback_query(call.id)
    except: pass

    # Check Channel Join Status
    if not check_user_joined(chat_id):
        # Delete the old welcome card or edit it to prompt join
        try:
            bot.delete_message(chat_id=chat_id, message_id=call.message.message_id)
        except: pass
        prompt_join_channels(chat_id)
        return

    # Check credits (if paid mode)
    if stats_manager.get_bot_mode() == "paid":
        credits = stats_manager.get_user_credits(chat_id)
        if credits <= 0:
            send_zero_credits_dashboard(chat_id, message_id=call.message.message_id)
            return

    # Step 3: Transition to the Mobile Verification card.
    user_states[chat_id] = {'step': 'AWAITING_MOBILE'}
    step1_text = get_ui_card(
        step_num="1",
        title="Mobile Verification",
        description="Please send the <b>10-digit Mobile Number</b> linked to Aadhaar."
    )
    try:
        bot.edit_message_text(
            chat_id=chat_id, message_id=call.message.message_id,
            text=step1_text, parse_mode='HTML'
        )
    except:
        bot.send_message(chat_id, step1_text, parse_mode='HTML')

def get_admin_dashboard_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Configuration Deck
    mode = stats_manager.get_bot_mode()
    mode_btn_text = "🔓 Toggle Mode: FREE" if mode == "free" else "🔒 Toggle Mode: PAID"
    btn_toggle_mode = types.InlineKeyboardButton(mode_btn_text, callback_data="admin_toggle_mode")
    btn_set_def_credits = types.InlineKeyboardButton("💳 Default Credits", callback_data="admin_set_default_credits")
    
    # New Dynamic Controls
    btn_sys_settings = types.InlineKeyboardButton("⚙️ System Settings", callback_data="admin_settings_menu")
    btn_view_recent_cracks = types.InlineKeyboardButton("👁 View Recent Cracks", callback_data="admin_view_recent_cracks")
    
    # Management Deck
    btn_grant_credits = types.InlineKeyboardButton("➕ Grant Credits", callback_data="admin_grant_credits")
    btn_broadcast = types.InlineKeyboardButton("📢 Broadcast Msg", callback_data="admin_broadcast")
    
    # Reports & Navigation Deck
    btn_view_users = types.InlineKeyboardButton("👥 View Users", callback_data="admin_view_users_page_1")
    btn_export_users = types.InlineKeyboardButton("📥 Export User List", callback_data="admin_download_users")
    
    btn_view_logs = types.InlineKeyboardButton("👁 View Error Logs", callback_data="admin_view_logs")
    btn_export_logs = types.InlineKeyboardButton("📥 Export Error Logs", callback_data="admin_download_logs")
    
    btn_cracked = types.InlineKeyboardButton("📂 Download Cracked Database", callback_data="admin_download_cracked")
    btn_stats = types.InlineKeyboardButton("🔄 Refresh Console", callback_data="admin_stats")
    
    # Arrange in a gorgeous, app-like visual grid
    markup.add(btn_toggle_mode, btn_set_def_credits)
    markup.add(btn_sys_settings, btn_view_recent_cracks)
    markup.add(btn_grant_credits, btn_broadcast)
    markup.add(btn_view_users, btn_export_users)
    markup.add(btn_view_logs, btn_export_logs)
    markup.add(btn_cracked)
    markup.add(btn_stats)
    return markup

def send_admin_dashboard(chat_id):
    summary = stats_manager.get_stats_summary(user_states)
    markup = get_admin_dashboard_markup()
    bot.send_message(chat_id, summary, reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_callbacks(call):
    chat_id = call.message.chat.id
    if chat_id not in ADMIN_IDS:
        try: bot.answer_callback_query(call.id, "Access Denied!")
        except: pass
        return
        
    try: bot.answer_callback_query(call.id)
    except: pass
    
    action = call.data
    if action == "admin_stats":
        summary = stats_manager.get_stats_summary(user_states)
        markup = get_admin_dashboard_markup()
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=summary, reply_markup=markup, parse_mode='HTML')
        except: pass
        
    elif action == "admin_settings_menu":
        cooldown = stats_manager.get_cooldown_seconds()
        max_concurrent = stats_manager.get_max_concurrent_tasks()
        settings_text = (
            "⚙️ <b>SYSTEM CONFIGURATION SETTINGS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ Cooldown Timer:  <b>{cooldown}s</b>\n"
            f"⚡ Max Concurrency:  <b>{max_concurrent} tasks</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Choose a setting to adjust below:"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_cooldown = types.InlineKeyboardButton(f"⏳ Cooldown ({cooldown}s)", callback_data="admin_set_cooldown")
        btn_concurrency = types.InlineKeyboardButton(f"⚡ Max Concurrent ({max_concurrent})", callback_data="admin_set_concurrent")
        btn_back = types.InlineKeyboardButton("🔙 Back to Main", callback_data="admin_stats")
        markup.add(btn_cooldown, btn_concurrency)
        markup.add(btn_back)
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=settings_text, reply_markup=markup, parse_mode='HTML')
        except: pass

    elif action == "admin_set_cooldown":
        user_states[chat_id] = {'step': 'AWAITING_ADMIN_COOLDOWN'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id, "⏳ <b>Set Global Cooldown</b>\n\n👇 Please enter the global cooldown period in seconds:\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "admin_set_concurrent":
        user_states[chat_id] = {'step': 'AWAITING_ADMIN_MAX_CONCURRENT'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id, "⚡ <b>Set Max Concurrency Limit</b>\n\n👇 Please enter the maximum number of concurrent tasks allowed:\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "admin_view_recent_cracks":
        data = stats_manager.load_stats()
        history = data.get("cracked_history", [])
        recent = history[-5:]
        msg_text = "👁 <b>RECENT CRACKED DETAILS (Last 5)</b>\n"
        msg_text += "━━━━━━━━━━━━━━━━━━━━━━\n"
        if not recent:
            msg_text += "<i>No successful crack history found in database.</i>\n"
        else:
            for idx, record in enumerate(reversed(recent), 1):
                timestamp = record.get("timestamp", "N/A")
                fname = record.get("first_name", "N/A")
                uname = record.get("username", "N/A")
                hname = record.get("name", "N/A")
                mobile_num = record.get("mobile", "N/A")
                uid_num = record.get("uid", "N/A")
                pwd = record.get("password", "N/A")
                eid_num = record.get("eid", "N/A")
                uname_str = f" (@{uname})" if uname and uname != "N/A" else ""
                msg_text += (
                    f"🎯 <b>{idx}. {hname}</b>\n"
                    f"  ├─ 📅 Time: <code>{timestamp}</code>\n"
                    f"  ├─ 👤 User: {fname}{uname_str}\n"
                    f"  ├─ 📞 Mobile: <code>{mobile_num}</code>\n"
                    f"  ├─ 🆔 EID: <code>{eid_num}</code>\n"
                    f"  ├─ 🔑 Aadhaar: <code>{uid_num}</code>\n"
                    f"  └─ 🔓 Password: <code>{pwd}</code>\n"
                    f"──────────────────────\n"
                )
        msg_text += "━━━━━━━━━━━━━━━━━━━━━━"
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_refresh = types.InlineKeyboardButton("🔄 Refresh Feed", callback_data="admin_view_recent_cracks")
        btn_back = types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_stats")
        markup.add(btn_refresh, btn_back)
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=msg_text, reply_markup=markup, parse_mode='HTML')
        except: pass
        
    elif action == "admin_toggle_mode":
        current_mode = stats_manager.get_bot_mode()
        new_mode = "paid" if current_mode == "free" else "free"
        stats_manager.set_bot_mode(new_mode)
        summary = stats_manager.get_stats_summary(user_states)
        markup = get_admin_dashboard_markup()
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=summary, reply_markup=markup, parse_mode='HTML')
        except: pass

    elif action == "admin_set_default_credits":
        user_states[chat_id] = {'step': 'AWAITING_ADMIN_DEFAULT_CREDITS'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id, "💳 <b>Set Default Credits</b>\n\n👇 Please enter the default credits count for new users:\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')
        
    elif action == "admin_grant_credits":
        user_states[chat_id] = {'step': 'AWAITING_ADMIN_GRANT_USER_ID'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id, "➕ <b>Grant User Credits</b>\n\n👇 Please enter the Telegram User ID (Chat ID) of the target user:\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')

    elif action == "admin_broadcast":
        user_states[chat_id] = {'step': 'AWAITING_BROADCAST_MSG'}
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id, "📢 <b>Broadcast Command Triggered</b>\n\n👇 Kripya niche text, image, document ya forward message send karein jo aap saare bot users ko bhejna chahte hain.\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')
        
    elif action == "admin_download_cracked":
        bot.send_message(chat_id, "⏳ <b>Fetching Cracked Data Database Report...</b>", parse_mode='HTML')
        import shutil
        permanent_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cracked_history.txt")
        temp_report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cracked_history_temp.txt")
        
        if os.path.exists(permanent_path) and os.path.getsize(permanent_path) > 0:
            try:
                shutil.copy(permanent_path, temp_report_path)
                report_path = temp_report_path
            except Exception as e:
                print(f"⚠️ Failed to copy permanent cracked history: {e}")
                report_path = stats_manager.get_cracked_data_file_path()
        else:
            report_path = stats_manager.get_cracked_data_file_path()
            
        if report_path and os.path.exists(report_path):
            with open(report_path, 'rb') as f:
                bot.send_document(chat_id, f, caption="📂 <b>Cracked Aadhaar Database Log</b>")
            try: os.remove(report_path)
            except: pass
        else:
            bot.send_message(chat_id, "❌ Failed to generate report or database is empty.", parse_mode='HTML')
            
    elif action == "admin_download_users":
        bot.send_message(chat_id, "⏳ <b>Generating User List...</b>", parse_mode='HTML')
        data = stats_manager.load_stats()
        users = data.get("users", [])
        def_credits = stats_manager.get_default_credits()
        if not users:
            bot.send_message(chat_id, "❌ No registered users found in the database.", parse_mode='HTML')
        else:
            users_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users_list.txt")
            with open(users_file, 'w', encoding='utf-8') as f:
                f.write(f"🔒 REGISTERED BOT USERS REPORT ({len(users)} total)\n")
                f.write("============================================================\n\n")
                for idx, u in enumerate(users, 1):
                    if isinstance(u, dict):
                        cid = u.get("chat_id", "N/A")
                        fname = u.get("first_name", "N/A")
                        uname = u.get("username", "N/A")
                        joined = u.get("joined", "N/A")
                        credits = u.get("credits", def_credits)
                        uname_str = f" (@{uname})" if uname and uname != "N/A" else ""
                        f.write(f"{idx}. 👤 {fname}{uname_str}\n   🆔 ID: {cid} | 💳 Credits: {credits} | 📅 Joined: {joined}\n\n")
                    else:
                        f.write(f"{idx}. 🆔 User ID: {u}\n\n")
            with open(users_file, 'rb') as f:
                bot.send_document(chat_id, f, caption=f"👤 <b>Registered Bot Users List ({len(users)} users)</b>")
            try: os.remove(users_file)
            except: pass
 
    elif action == "admin_download_logs":
        bot.send_message(chat_id, "⏳ <b>Fetching Secure Error Logs...</b>", parse_mode='HTML')
        log_path = stats_manager.get_error_log_file_path()
        if log_path and os.path.exists(log_path):
            with open(log_path, 'rb') as f:
                bot.send_document(chat_id, f, caption="⚠️ <b>Aadhaar Bot User Error Logs</b>")
        else:
            bot.send_message(chat_id, "✅ No user errors have been logged yet or log file is empty.", parse_mode='HTML')

    elif action.startswith("admin_view_users_page_"):
        try:
            page = int(action.split("_")[-1])
        except:
            page = 1
            
        data = stats_manager.load_stats()
        users = data.get("users", [])
        
        if not users:
            try:
                bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="❌ No registered users found in the database.", reply_markup=get_admin_dashboard_markup(), parse_mode='HTML')
            except: pass
            return
            
        PAGE_SIZE = 5
        total_users = len(users)
        total_pages = max(1, (total_users + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(1, min(page, total_pages))
        start_idx = (page - 1) * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        page_users = users[start_idx:end_idx]
        
        msg_text = f"👥 <b>USER MANAGEMENT DECK (Page {page}/{total_pages})</b>\n"
        msg_text += "━━━━━━━━━━━━━━━━━━━━━━\n"
        
        def_credits = stats_manager.get_default_credits()
        for idx, u in enumerate(page_users, start=start_idx + 1):
            if isinstance(u, dict):
                cid = u.get("chat_id", "N/A")
                fname = u.get("first_name", "N/A")
                uname = u.get("username", "N/A")
                joined = u.get("joined", "N/A")
                credits = u.get("credits", def_credits)
                
                uname_str = f" (@{uname})" if uname and uname != "N/A" else ""
                credit_status = f"<code>{credits} 💳</code>" if credits > 0 else "<code>0 💳</code> (Exhausted ❌)"
                
                msg_text += (
                    f"👤 <b>{idx}. {fname}</b>{uname_str}\n"
                    f"  ├─ 🆔 ID: <code>{cid}</code>\n"
                    f"  ├─ 💳 Balance: {credit_status}\n"
                    f"  └─ 📅 Joined: <code>{joined}</code>\n\n"
                )
            else:
                msg_text += f"🆔 User ID: <code>{u}</code>\n──────────────────────\n\n"
                
        msg_text += "━━━━━━━━━━━━━━━━━━━━━━\n"
        msg_text += f"Total registered users: <b>{total_users}</b>"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        nav_buttons = []
        if page > 1:
            nav_buttons.append(types.InlineKeyboardButton("⬅️ Previous", callback_data=f"admin_view_users_page_{page-1}"))
        if page < total_pages:
            nav_buttons.append(types.InlineKeyboardButton("➡️ Next", callback_data=f"admin_view_users_page_{page+1}"))
            
        if nav_buttons:
            markup.add(*nav_buttons)
            
        btn_export = types.InlineKeyboardButton("📥 Export Users List", callback_data="admin_download_users")
        btn_back = types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_stats")
        markup.add(btn_export, btn_back)
        
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=msg_text, reply_markup=markup, parse_mode='HTML')
        except Exception as e:
            print(f"⚠️ [ADMIN] Error editing message to show users: {e}")
 
    elif action == "admin_view_logs":
        log_path = stats_manager.get_error_log_file_path()
        if not log_path or not os.path.exists(log_path):
            msg_text = "✅ <b>No user errors have been logged yet or log file is empty.</b>"
        else:
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Fetch last 10 error lines
                last_lines = [line.strip() for line in lines if line.strip()][-10:]
                
                msg_text = f"⚠️ <b>SYSTEM DIAGNOSTIC LOGS (Last {len(last_lines)})</b>\n"
                msg_text += "━━━━━━━━━━━━━━━━━━━━━━\n"
                
                for line in last_lines:
                    # Log format: [TIMESTAMP] User: FIRSTNAME (@USERNAME) [ID: CHATID] | Error: MSG
                    try:
                        timestamp_part, rest = line.split("] User: ", 1)
                        timestamp = timestamp_part.replace("[", "")
                        user_info_part, error_part = rest.split(" | Error: ", 1)
                        
                        msg_text += (
                            f"📅 <code>{timestamp}</code>\n"
                            f"👤 <b>User:</b> <code>{user_info_part}</code>\n"
                            f"❌ <b>Error:</b> <code>{error_part}</code>\n"
                            f"──────────────────────\n"
                        )
                    except:
                        msg_text += f"▪️ <code>{line}</code>\n──────────────────────\n"
                
                msg_text += "━━━━━━━━━━━━━━━━━━━━━━"
            except Exception as e:
                msg_text = f"❌ <b>Error reading log file:</b> <code>{e}</code>"
                
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_refresh = types.InlineKeyboardButton("🔄 Refresh Logs", callback_data="admin_view_logs")
        btn_export = types.InlineKeyboardButton("📥 Export Logs", callback_data="admin_download_logs")
        btn_back = types.InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_stats")
        markup.add(btn_refresh, btn_export)
        markup.add(btn_back)
        
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=msg_text, reply_markup=markup, parse_mode='HTML')
        except Exception as e:
            print(f"⚠️ [ADMIN] Error editing message to show logs: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('mp|'))
def handle_manual_pref_selection(call):
    chat_id = call.message.chat.id
    try: bot.answer_callback_query(call.id)
    except: pass
    
    parts = call.data.split('|')
    action = parts[1]
    
    state = user_states.get(chat_id, {})
    number = state.get('num', '')
    
    if action == 'manual':
        user_states[chat_id] = {'step': 'AWAITING_NAME', 'num': number, 'prefix': ''}
        prompt_text = "Send me the <b>Aadhaar Holder Name</b> exactly as printed on the card."
        msg_text = get_ui_card(
            step_num="2",
            title="Aadhaar Holder Name",
            description=prompt_text,
            target=number
        )
        try:
            bot.edit_message_text(
                chat_id=chat_id, message_id=call.message.message_id,
                text=msg_text, parse_mode='HTML'
            )
        except:
            bot.send_message(chat_id, msg_text, parse_mode='HTML')
    else:
        # Male or Female selected directly -> Bypass Name and DOB steps!
        name = "Mr" if action == "Mr." else "Mrs"
        dob = None
        
        status_msg = get_ui_card(
            step_num="3",
            title="EID Retrieval",
            description=f"⏳ <b>Initializing target {number}...</b>\n\nPlease wait..."
        )
        try:
            bot.edit_message_text(
                chat_id=chat_id, message_id=call.message.message_id,
                text=status_msg, parse_mode='HTML'
            )
        except:
            bot.send_message(chat_id, status_msg, parse_mode='HTML')
            
        user_states[chat_id] = {'step': 'PROCESSING'}
        
        user_info = {
            'username': call.from_user.username or 'N/A',
            'first_name': call.from_user.first_name or 'N/A'
        }
        
        asyncio.run_coroutine_threadsafe(execute_and_reset(chat_id, name, number, dob, user_info=user_info), loop)


@bot.callback_query_handler(func=lambda call: call.data == 'refresh_zero_credits')
def handle_refresh_zero_credits(call):
    chat_id = call.message.chat.id
    try:
        bot.answer_callback_query(call.id, text="Checking credits...", show_alert=False)
    except: pass
    
    is_admin = chat_id in ADMIN_IDS
    mode = stats_manager.get_bot_mode()
    
    if is_admin or mode == "free":
        send_welcome_dashboard(chat_id, message_id=call.message.message_id)
        return
        
    credits = stats_manager.get_user_credits(chat_id)
    if credits > 0:
        try:
            bot.send_message(chat_id, f"🎉 <b>Credits Received!</b> Aapke account me {credits} credits aa gaye hain.", parse_mode='HTML')
        except: pass
        send_welcome_dashboard(chat_id, message_id=call.message.message_id)
    else:
        send_zero_credits_dashboard(chat_id, message_id=call.message.message_id)
        try:
            bot.answer_callback_query(call.id, text="Still 0 credits. Invite friends or contact admin.", show_alert=True)
        except: pass


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    print(f"📥 [CALLBACK] Generic callback triggered: {call.data} for chat_id: {chat_id}")
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"⚠️ [CALLBACK] Failed to answer generic callback: {e}")

    if call.data == "check_joined_status":
        if check_user_joined(chat_id):
            try:
                bot.delete_message(chat_id=chat_id, message_id=call.message.message_id)
            except: pass
            send_welcome_dashboard(chat_id)
        else:
            try:
                bot.answer_callback_query(call.id, text="⚠️ Aapne abhi tak saare channels join nahi kiye hain!", show_alert=True)
            except: pass


@bot.message_handler(commands=['profile'])
def handle_profile(message):
    chat_id = message.chat.id
    
    # Check Channel Join Status
    if not check_user_joined(chat_id):
        prompt_join_channels(chat_id)
        return
        
    try:
        str_chat_id = int(chat_id)
    except:
        str_chat_id = chat_id
        
    data = stats_manager.load_stats()
    
    # Find user in users list
    user_record = None
    for u in data.get("users", []):
        if isinstance(u, dict) and u.get("chat_id") == str_chat_id:
            user_record = u
            break
            
    # Fallback or create if not exists
    if not user_record:
        try:
            stats_manager.register_visit(chat_id, username=message.from_user.username, first_name=message.from_user.first_name)
            data = stats_manager.load_stats()
            for u in data.get("users", []):
                if isinstance(u, dict) and u.get("chat_id") == str_chat_id:
                    user_record = u
                    break
        except: pass
                
    join_date = user_record.get("joined", "N/A") if user_record else "N/A"
    credits = stats_manager.get_user_credits(chat_id)
    mode = stats_manager.get_bot_mode()
    
    # Count success cracks from history
    history = data.get("cracked_history", [])
    success_count = sum(1 for r in history if r.get("chat_id") == str_chat_id)
    
    credits_str = "Unlimited 💳" if mode == "free" else f"{credits} 💳"
    
    profile_text = (
        "👤 <b>USER PROFILE DASHBOARD</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  ├─ <b>First Name:</b> {message.from_user.first_name}\n"
        f"  ├─ <b>Username:</b> @{message.from_user.username or 'N/A'}\n"
        f"  ├─ <b>Telegram ID:</b> <code>{chat_id}</code>\n"
        f"  ├─ <b>Joined Date:</b> <code>{join_date}</code>\n"
        f"  ├─ <b>Credit Balance:</b> <b>{credits_str}</b>\n"
        f"  └─ <b>Success Checked:</b> <code>{success_count} ✅</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    bot.send_message(chat_id, profile_text, parse_mode='HTML')

@bot.message_handler(commands=['refer'])
def handle_refer(message):
    chat_id = message.chat.id
    
    # Check Channel Join Status
    if not check_user_joined(chat_id):
        prompt_join_channels(chat_id)
        return
        
    try:
        bot_username = bot.get_me().username
    except Exception as e:
        print(f"⚠️ Failed to get bot username: {e}")
        bot_username = "bot"
        
    referral_link = f"https://t.me/{bot_username}?start=ref_{chat_id}"
    
    data = stats_manager.load_stats()
    referred_count = 0
    for u in data.get("users", []):
        if isinstance(u, dict) and u.get("referred_by") == chat_id:
            referred_count += 1
            
    refer_text = (
        "🤝 <b>REFERRAL & INVITE SYSTEM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Apne dosto ko bot par invite karein aur har successful join par <b>1 Credit</b> payein!\n\n"
        "🔗 <b>Your Invite Link:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"👥 <b>Total Referrals:</b> <code>{referred_count} joined</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Tip: Click the link above to copy it and share.</i>"
    )
    bot.send_message(chat_id, refer_text, parse_mode='HTML')

@bot.message_handler(commands=['admin'])
def handle_admin(message):
    chat_id = message.chat.id
    if chat_id not in ADMIN_IDS:
        bot.send_message(chat_id, "❌ <b>Access Denied!</b>\nThis command is restricted to bot administrators only.", parse_mode='HTML')
        return
    send_admin_dashboard(chat_id)

def perform_broadcast(message):
    admin_chat_id = message.chat.id
    data = stats_manager.load_stats()
    users = data.get("users", [])
    
    success = 0
    failed = 0
    total = len(users)
    
    if total == 0:
        bot.send_message(admin_chat_id, "⚠️ Broadcast completed: No users found in database.")
        return
        
    start_time = time.time()
    for u in users:
        if isinstance(u, dict):
            user_id = u.get("chat_id")
        else:
            user_id = u
        if not user_id:
            continue
        try:
            bot.copy_message(chat_id=user_id, from_chat_id=admin_chat_id, message_id=message.message_id)
            success += 1
            time.sleep(0.05) # 20 messages per second rate limiting
        except Exception as e:
            print(f"⚠️ [BROADCAST] Failed to send to {user_id}: {e}")
            failed += 1
            
    elapsed = int(time.time() - start_time)
    report = (
        "📢 <b>Broadcast Completed!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Total Targeted:</b> <code>{total}</code>\n"
        f"✅ <b>Successfully Sent:</b> <code>{success}</code>\n"
        f"❌ <b>Failed / Blocked:</b> <code>{failed}</code>\n"
        f"⏱ <b>Time Taken:</b> <code>{elapsed} sec</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    bot.send_message(admin_chat_id, report, parse_mode='HTML')

@bot.message_handler(content_types=['text', 'photo', 'audio', 'video', 'document', 'sticker', 'voice', 'location', 'contact', 'video_note', 'animation'])
def handle_all(message):
    chat_id = message.chat.id
    try:
        stats_manager.register_visit(chat_id)
    except Exception as e:
        print(f"⚠️ [STATS] Failed to register visit: {e}")

    # If the user has not joined the required channels, block commands and text input
    if message.text and message.text.strip().startswith('/start'):
        # Let the /start command handler process this itself
        pass
    elif not check_user_joined(chat_id):
        prompt_join_channels(chat_id)
        return
        
    state = user_states.get(chat_id, {})
    str_chat_id = str(chat_id)
    
    # Broadcast Message Interceptor
    if state.get('step') == 'AWAITING_BROADCAST_MSG':
        text_val = message.text.strip() if message.text else ""
        if text_val.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Broadcast cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
            
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, "🚀 <b>Broadcast started in background...</b>\nUsers ko delivery messages report send ki jayegi.", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        
        # Start broadcasting in background thread
        threading.Thread(target=perform_broadcast, args=(message,), daemon=True).start()
        return

    # Guard: ignore non-text messages (photos, stickers, voice notes, etc.)
    if not message.text:
        return
    text = message.text.strip()
    
    # --- ADMIN CONFIGURATION & CREDIT SYSTEM INTERCEPTORS ---
    if state.get('step') == 'AWAITING_ADMIN_COOLDOWN':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
            
        if not text.isdigit():
            bot.send_message(chat_id, "⚠️ Invalid number. Please send an integer value:")
            return
            
        val = int(text)
        stats_manager.set_cooldown_seconds(val)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, f"✅ Global cooldown set to <b>{val}s</b> successfully!", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    if state.get('step') == 'AWAITING_ADMIN_MAX_CONCURRENT':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
            
        if not text.isdigit():
            bot.send_message(chat_id, "⚠️ Invalid number. Please send an integer value:")
            return
            
        val = int(text)
        stats_manager.set_max_concurrent_tasks(val)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, f"✅ Max concurrency limit set to <b>{val}</b> successfully!", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    if state.get('step') == 'AWAITING_ADMIN_DEFAULT_CREDITS':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
            
        if not text.isdigit():
            bot.send_message(chat_id, "⚠️ Invalid number. Please send an integer value:")
            return
            
        count = int(text)
        stats_manager.set_default_credits(count)
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, f"✅ Default credits set to <b>{count}</b> successfully!", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    if state.get('step') == 'AWAITING_ADMIN_GRANT_USER_ID':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
            
        if not text.isdigit():
            bot.send_message(chat_id, "⚠️ Invalid User ID. Please send a valid numeric Telegram Chat ID:")
            return
            
        target_id = int(text)
        user_states[chat_id] = {
            'step': 'AWAITING_ADMIN_GRANT_AMOUNT',
            'target_user_id': target_id
        }
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        cancel_markup.add("Cancel")
        bot.send_message(chat_id, f"➕ <b>Grant User Credits to ID:</b> <code>{target_id}</code>\n\n👇 Please enter the number of credits to add (e.g. 5, or negative value like -2 to deduct):\n\nType <b>Cancel</b> to abort.", reply_markup=cancel_markup, parse_mode='HTML')
        return

    if state.get('step') == 'AWAITING_ADMIN_GRANT_AMOUNT':
        if text.lower() == 'cancel':
            user_states[chat_id] = {'step': 'IDLE'}
            bot.send_message(chat_id, "❌ Action cancelled.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_dashboard(chat_id)
            return
            
        is_negative = text.startswith('-')
        clean_val = text[1:] if is_negative else text
        if not clean_val.isdigit():
            bot.send_message(chat_id, "⚠️ Invalid amount. Please send a numeric integer value:")
            return
            
        amount = int(clean_val)
        if is_negative:
            amount = -amount
            
        target_id = state.get('target_user_id')
        new_bal = stats_manager.add_user_credits(target_id, amount)
        
        user_states[chat_id] = {'step': 'IDLE'}
        bot.send_message(chat_id, f"✅ Successfully updated credits for user <code>{target_id}</code>.\n💳 Added: <b>{amount}</b>\n💳 New Balance: <b>{new_bal}</b>", parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
        send_admin_dashboard(chat_id)
        return

    # Session Cancellation Interceptor
    if text.lower() in ['/cancel', 'cancel', 'reset', '/reset']:
        # 1. Terminate pending captcha/OTP registry locks and clear buffers
        if str_chat_id in aadhaar_engine.user_page_registry:
            aadhaar_engine.user_page_registry[str_chat_id]['value'] = '__CANCEL__'
        aadhaar_engine.buffered_inputs.pop(str_chat_id, None)

            
        # 3. Terminate active Aadhaar engines and tasks
        if str_chat_id in aadhaar_engine.active_engines:
            eng = aadhaar_engine.active_engines.pop(str_chat_id, None)
            if eng:
                try: asyncio.run_coroutine_threadsafe(eng.close(), loop)
                except: pass
        if str_chat_id in aadhaar_engine.active_tasks:
            try: aadhaar_engine.active_tasks.remove(str_chat_id)
            except: pass
            
        # 4. Reset User States to IDLE
        user_states[chat_id] = {'step': 'IDLE'}
        
        cancel_text = (
            "❌ <b>Process Cancelled Successfully!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Aapka active session cancel kar diya gaya hai."
        )
        bot.send_message(chat_id, cancel_text, parse_mode='HTML')
        
        send_welcome_dashboard(chat_id)
        return
    
    # Priority Override: If input is a Target Mobile Number or start command with mobile number
    import re
    
    is_group = chat_id < 0
    starts_with_cmd = text.lower().startswith(('/aadhaar', '/aadhar'))
    
    extracted_target = None
    
    if is_group:
        # In groups, we ONLY trigger if it starts with /aadhaar or /aadhar
        if starts_with_cmd:
            # Remove the command prefix
            cmd_len = len('/aadhaar') if text.lower().startswith('/aadhaar') else len('/aadhar')
            number_part = text[cmd_len:].strip()
            
            # Clean and extract 10-digit number from number_part
            clean_num = re.sub(r'\D', '', number_part)
            if len(clean_num) == 10 and clean_num[0] in '6789':
                extracted_target = clean_num
            elif len(clean_num) > 10 and (number_part.startswith('+91') or clean_num.startswith(('91', '0'))):
                possible_target = clean_num[-10:]
                if possible_target[0] in '6789':
                    extracted_target = possible_target
    else:
        # In private chat, we trigger if it starts with command OR contains a number directly
        if starts_with_cmd:
            cmd_len = len('/aadhaar') if text.lower().startswith('/aadhaar') else len('/aadhar')
            number_part = text[cmd_len:].strip()
            clean_num = re.sub(r'\D', '', number_part)
            if len(clean_num) == 10 and clean_num[0] in '6789':
                extracted_target = clean_num
            elif len(clean_num) > 10 and (number_part.startswith('+91') or clean_num.startswith(('91', '0'))):
                possible_target = clean_num[-10:]
                if possible_target[0] in '6789':
                    extracted_target = possible_target
        else:
            # Directly sent number in private chat
            clean_num = re.sub(r'\D', '', text)
            if len(clean_num) == 10 and clean_num[0] in '6789':
                extracted_target = clean_num
            elif len(clean_num) > 10 and (text.startswith('+91') or clean_num.startswith(('91', '0'))):
                possible_target = clean_num[-10:]
                if possible_target[0] in '6789':
                    extracted_target = possible_target

    if extracted_target:
        # Check credits before pre-warming (if paid mode)
        if stats_manager.get_bot_mode() == "paid":
            credits = stats_manager.get_user_credits(chat_id)
            if credits <= 0:
                send_zero_credits_dashboard(chat_id)
                return

        # Check if record is already cracked in history
        cached_record = stats_manager.find_cracked_record(extracted_target)
        if cached_record:
            # Deduct credit if bot mode is paid
            if stats_manager.get_bot_mode() == "paid":
                stats_manager.deduct_user_credit(chat_id)
                
            name = cached_record.get("name", "N/A")
            uid = cached_record.get("uid", "N/A")
            password = cached_record.get("password", "N/A")
            eid = cached_record.get("eid", "N/A")
            
            cached_text = (
                "🎉 <b>Record Found in Database! (Instant Retrieval)</b>\n\n"
                f"👤 <b>Name:</b> <code>{name}</code>\n"
                f"📞 <b>Mobile:</b> <code>{extracted_target}</code>\n"
                f"🆔 <b>EID:</b> <code>{eid}</code>\n"
                f"🔢 <b>Aadhaar Number:</b> <code>{uid}</code>\n"
                f"🔑 <b>Password:</b> <code>{password}</code>\n\n"
                "⚡ <i>Data locally retrieved instantly without contacting UIDAI servers.</i>"
            )
            bot.send_message(chat_id, cached_text, parse_mode='HTML')
            
            # Try to send the unlocked PDF copy if it exists in the cracked directory
            try:
                safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
                safe_uid = uid.replace(' ', '')
                pdf_path = os.path.join(aadhaar_engine.CRACKED_DIR, f"{safe_name}_{safe_uid}.pdf")
                if os.path.exists(pdf_path):
                    with open(pdf_path, 'rb') as f:
                        bot.send_document(chat_id, f, caption=f"📄 <b>Aadhaar PDF (Unlocked)</b>")
            except Exception as e_pdf:
                print(f"⚠️ [CACHE] Failed to send cached PDF: {e_pdf}")
                
            send_welcome_dashboard(chat_id)
            return

        print(f"🔄 Override: Preempting tasks for {chat_id} -> starting fresh target {extracted_target}")
        
        # 1. Clear prompt/OTP registry lock and buffer
        aadhaar_engine.user_page_registry.pop(str_chat_id, None)
        aadhaar_engine.buffered_inputs.pop(str_chat_id, None)
        
        # 2. Terminate old Aadhaar Engine processes if active
        if str_chat_id in aadhaar_engine.active_engines:
            eng = aadhaar_engine.active_engines.pop(str_chat_id, None)
            if eng:
                try: asyncio.run_coroutine_threadsafe(eng.close(), loop)
                except: pass
        if str_chat_id in aadhaar_engine.active_tasks:
            try: aadhaar_engine.active_tasks.remove(str_chat_id)
            except: pass
            
        # Pre-warm Aadhaar portals early (both retrieve EID and download Aadhaar)
        aadhaar_engine.prewarm_engine(bot, chat_id, extracted_target)
            
        # 3. Present prefix selection buttons immediately
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_male = types.InlineKeyboardButton("👨 Male", callback_data="mp|Mr.")
        btn_female = types.InlineKeyboardButton("👩 Female", callback_data="mp|Mrs.")
        btn_manual = types.InlineKeyboardButton("✏️ Enter Name Manually", callback_data="mp|manual")
        markup.add(btn_male, btn_female)
        markup.add(btn_manual)
        
        msg_text = get_ui_card(
            step_num="2",
            title="Gender / Prefix Selection",
            description="👇 <b>Select the gender/prefix of the Aadhaar holder:</b>",
            target=extracted_target,
            show_tip=True
        )
        
        bot.send_message(chat_id, msg_text, reply_markup=markup, parse_mode='HTML')
        user_states[chat_id] = {'step': 'AWAITING_MANUAL_PREF_SELECTION', 'num': extracted_target}
        return

    # Check for Captcha/OTP Input from Engine
    if str_chat_id in aadhaar_engine.user_page_registry and aadhaar_engine.user_page_registry[str_chat_id].get('value') is None:
        aadhaar_engine.user_page_registry[str_chat_id]['value'] = text
        if chat_id < 0:
            try: bot.delete_message(chat_id, message.message_id)
            except: pass
        return
    elif state.get('step') == 'PROCESSING':
        # Buffer this message as it might be an OTP sent during the race window before wait_for_input starts
        aadhaar_engine.buffered_inputs[str_chat_id] = text
        if chat_id < 0:
            try: bot.delete_message(chat_id, message.message_id)
            except: pass
        return



    if state.get('step') == 'AWAITING_NAME':
        prefix = state.get('prefix', '')
        name = f"{prefix}{text}".strip()
        num = state.get('num', '')
        
        status_msg = get_ui_card(
            step_num="3",
            title="EID Retrieval",
            description=f"⏳ <b>Initializing target {num}...</b>\n\nPlease wait..."
        )
        bot.send_message(chat_id, status_msg, parse_mode='HTML')
        user_states[chat_id]['step'] = 'PROCESSING'
        user_info = {
            'username': message.from_user.username or 'N/A',
            'first_name': message.from_user.first_name or 'N/A'
        }
        
        dob = None
        asyncio.run_coroutine_threadsafe(execute_and_reset(chat_id, name, num, dob, user_info=user_info), loop)
        return

async def execute_and_reset(chat_id, name, num, dob, user_info=None):
    task_started = False
    try:
        # Check permissions/limits right before executing the task
        is_admin = chat_id in ADMIN_IDS
        
        # Check credits one final time (if paid mode)
        if stats_manager.get_bot_mode() == "paid":
            credits = stats_manager.get_user_credits(chat_id)
            if credits <= 0:
                send_zero_credits_dashboard(chat_id)
                # Reset user state back to IDLE
                user_states[chat_id] = {'step': 'IDLE'}
                return
                    
        # Check global cooldown for non-admins
        if not is_admin:
            allowed, remaining_seconds = stats_manager.check_global_cooldown()
            if not allowed:
                cooldown_msg = (
                    "⏳ <b>Bot Cooldown Active!</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "UIDAI server limit ki wajah se, bot abhi cooldown period me hai.\n\n"
                    f"🕒 Kripya <b>{remaining_seconds} seconds</b> ke baad phir se try karein."
                )
                bot.send_message(chat_id, cooldown_msg, parse_mode='HTML')
                # Reset user state back to IDLE
                user_states[chat_id] = {'step': 'IDLE'}
                send_welcome_dashboard(chat_id)
                return
                
        # If allowed and user is not admin, activate the global cooldown
        if not is_admin:
            stats_manager.update_global_run_time()

        task_started = await aadhaar_engine.execute_task(bot, chat_id, name, num, dob, user_info=user_info)
    except Exception as e:
        print(f"❌ [execute_and_reset] Task error: {e}")
        try:
            stats_manager.log_error(chat_id, user_info, f"execute_and_reset: {e}")
        except: pass
    finally:
        if task_started:
            user_states[chat_id] = {'step': 'IDLE'}
            # Show welcome back dashboard so user isn't left hanging after completion
            try:
                send_welcome_dashboard(chat_id)
            except: pass


def cleanup_temp_files():
    """Sweeps and deletes any leftover temporary files or browser caches on startup to optimize storage."""
    print("🧹 [CLEANUP] Sweeping residual temporary files...")
    import shutil
    
    # 1. Clean temp captcha files from project root
    prefixes = ['temp_captcha_', 'cap_ui_', 'cap_um_']
    for file in os.listdir(BASE_DIR):
        if any(file.startswith(prefix) for prefix in prefixes):
            try:
                os.remove(os.path.join(BASE_DIR, file))
                print(f"🗑️ Cleaned temp file: {file}")
            except: pass

    # 2. Ensure cracked_aadhar output folder exists (recreate if deleted)
    cracked_dir = os.path.join(BASE_DIR, 'cracked_aadhar')
    os.makedirs(cracked_dir, exist_ok=True)
    print(f"📁 [CLEANUP] Output folder ready: {cracked_dir}")
            
    # 3. Clean temporary user data profile folders to save disk space
    bulk_dir = os.path.join(BASE_DIR, 'BULK_USER_DATA')
    if os.path.exists(bulk_dir):
        try:
            shutil.rmtree(bulk_dir, ignore_errors=True)
            print("🧹 Cleaned bulk user data directories.")
        except: pass

if __name__ == "__main__":
    # Clean leftover logs, captures, or profiles on startup
    cleanup_temp_files()
    
    loop = asyncio.new_event_loop()
    def run_loop(l):
        asyncio.set_event_loop(l)
        l.run_until_complete(aadhaar_engine.init_pool(bot))
        l.run_forever()
    
    threading.Thread(target=run_loop, args=(loop,), daemon=True).start()
    
    print("🤖 Bot is now LIVE.")
    


    # Infinite Polling Loop
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60, allowed_updates=['message', 'callback_query'])
        except Exception as e:
            print(f"⚠️ Polling Exception: {e}")
            time.sleep(5)
