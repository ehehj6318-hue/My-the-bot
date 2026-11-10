import asyncio
import os
import re
import subprocess
import base64
import ddddocr
import random
import uuid
import sys
from dotenv import load_dotenv
import time
import stats_manager

# Load environmental variables from .env file
load_dotenv()

# Force all spawned python subprocesses to use UTF-8 output encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'

DEVELOPER_USERNAME = os.getenv('DEVELOPER_USERNAME', '@ShadowCipherX1')

def escape_html(s):
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


# Global Registry for Interactivity
user_page_registry = {}
buffered_inputs = {}
_engine_instance = None
_running_loop = None
active_engines = {}  # chat_id -> AadhaarEngine instance
active_tasks = set() # Track chat_ids currently executing
VISIBLE_MODE = {} # chat_id: bool
CRACKED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cracked_aadhar")

# Always ensure output directory exists (recreates if user deletes it)
os.makedirs(CRACKED_DIR, exist_ok=True)

STICKERS = {
    "SUCCESS": "CAACAgIAAxkBAAEL6V9mAe7q-Q1R-O_0v57_5y7X-Q5_QAACSwADr8ZRGm_F-G7M7_9kNAQ"
}

def escape_html(text):
    """Escapes HTML special characters for Telegram."""
    return str(text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def parse_dob(date_str):
    """Parses DOB to DD-MM-YYYY format for UMANG."""
    if not date_str: return date_str
    
    months_map = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
        'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }
    
    # Clean and split
    clean = date_str.replace(',', '').strip()
    parts = re.split(r'[ /\-.]', clean)
    
    if len(parts) < 3:
        return date_str
    
    day, month, year = None, None, None

    # Identify Year (look for 4 digits)
    if len(parts[0]) == 4:
        year = parts[0]
        month = parts[1]
        day = parts[2]
    elif len(parts[2]) == 4:
        day = parts[0]
        month = parts[1]
        year = parts[2]
    else:
        # Fallback to simple split if no 4-digit year found
        day, month, year = parts[0], parts[1], parts[2]

    # Convert month name to number
    m_lower = str(month).lower()[:3]
    if m_lower in months_map:
        month = months_map[m_lower]
    
    try:
        return f"{str(day).zfill(2)}-{str(month).zfill(2)}-{year}"
    except:
        return date_str

async def init_pool(bot_instance):
    global _running_loop
    _running_loop = asyncio.get_running_loop()

class AadhaarEngine:
    def __init__(self, bot, chat_id=None):
        self.bot = bot
        self.chat_id = str(chat_id) if chat_id else None
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        self.status_msg_id = None
        self._preloader_active = False
        self._preloader_task = None
        self.temp_msg_ids = []

    def update_status(self, text):
        """Updates a single live status message dynamically to avoid spamming the chat."""
        if not self.chat_id or self.chat_id == "master":
            return
        footer = f"\n━━━━━━━━━━━━━━━━━━━━━━\n<i>Dev: @{DEVELOPER_USERNAME} | Dark Vendor</i>"
        if self.status_msg_id:
            try:
                self.bot.edit_message_text(chat_id=self.chat_id, message_id=self.status_msg_id, text=f"{text}{footer}", parse_mode='HTML')
            except: pass
        else:
            try:
                msg = self.bot.send_message(self.chat_id, f"{text}{footer}", parse_mode='HTML')
                self.status_msg_id = msg.message_id
                try:
                    if int(self.chat_id) < 0:
                        self.temp_msg_ids.append(self.status_msg_id)
                except: pass
            except: pass

    def refresh_status_card(self, text):
        """Deletes the old status message and spawns a new one at the very bottom of the chat."""
        if not self.chat_id or self.chat_id == "master":
            return
        if self.status_msg_id:
            try:
                self.bot.delete_message(chat_id=self.chat_id, message_id=self.status_msg_id)
            except: pass
            self.status_msg_id = None
        self.update_status(text)

    def start_preloader(self, base_text):
        """Starts a background task that animates a satisfying preloader under the status message."""
        self.stop_preloader()
        self._preloader_active = True
        self.preloader_base_text = base_text
        
        # Always use the global _running_loop to avoid wrong-loop errors with multiple users
        global _running_loop
        target_loop = _running_loop or asyncio.get_event_loop()
        self._preloader_task = target_loop.create_task(self._preloader_loop())

    def stop_preloader(self):
        """Stops the active background preloader task."""
        self._preloader_active = False
        if hasattr(self, '_preloader_task') and self._preloader_task:
            try:
                self._preloader_task.cancel()
            except: pass
            self._preloader_task = None

    async def _preloader_loop(self):
        # A super premium, satisfying CLI-style spinner & sliding block preloader!
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        bars = [
            "▒░░░░░░░░░",
            "█▒░░░░░░░░",
            "██▒░░░░░░░",
            "███▒░░░░░░",
            "████▒░░░░░",
            "█████▒░░░░",
            "██████▒░░░",
            "███████▒░░",
            "████████▒░",
            "█████████▒",
            "██████████"
        ]
        
        idx = 0
        bar_idx = 0
        direction = 1
        
        while self._preloader_active:
            try:
                spin = spinner[idx % len(spinner)]
                bar = bars[bar_idx]
                
                bar_idx += direction
                if bar_idx >= len(bars) or bar_idx < 0:
                    direction *= -1
                    bar_idx += direction
                
                base_text = getattr(self, 'preloader_base_text', '⏳ Processing...')
                full_text = f"{base_text}\n━━━━━━━━━━━━━━━━━━━━━━\n{spin} <b>{bar}</b>"
                footer = f"\n━━━━━━━━━━━━━━━━━━━━━━\n<i>Dev: @{DEVELOPER_USERNAME} | Dark Vendor</i>"
                
                if self.status_msg_id:
                    try:
                        self.bot.edit_message_text(
                            chat_id=self.chat_id,
                            message_id=self.status_msg_id,
                            text=f"{full_text}{footer}",
                            parse_mode='HTML'
                        )
                    except: pass
                
                idx += 1
                await asyncio.sleep(1.2)  # Safe sleep interval for Telegram limits
            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(2)

    async def close(self):
        """Properly shuts down any active EID subprocesses."""
        if self.chat_id == 'master':
            for uid, eng in list(active_engines.items()):
                try: await eng.close()
                except: pass
            active_engines.clear()
            active_tasks.clear()

        try:
            if hasattr(self, 'phase1_process') and self.phase1_process:
                try:
                    self.phase1_process.terminate()
                    print(f"🛑 [ENGINE] Terminated early Phase 1 process for {self.chat_id}.")
                except: pass
                self.phase1_process = None
            if hasattr(self, 'phase1_task') and self.phase1_task:
                try:
                    self.phase1_task.cancel()
                except: pass
                self.phase1_task = None
        except Exception as e:
            print(f"⚠️ [ENGINE] Error during shutdown: {e}")

    async def delete_temp_messages(self):
        """Deletes all intermediate captcha and status messages tracked in self.temp_msg_ids in group chats."""
        if not self.chat_id:
            return
        try:
            chat_id_int = int(self.chat_id)
        except ValueError:
            return
        
        if chat_id_int < 0:
            print(f"🧹 [CLEANUP] Deleting {len(self.temp_msg_ids)} intermediate messages in group {self.chat_id}...")
            for msg_id in list(self.temp_msg_ids):
                try:
                    self.bot.delete_message(chat_id=chat_id_int, message_id=msg_id)
                except Exception as e:
                    print(f"⚠️ [CLEANUP] Failed to delete message {msg_id}: {e}")
            self.temp_msg_ids.clear()



    def start_early_phase1(self, mobile):
        """Starts early Phase 1 subprocess in the background."""
        if hasattr(self, 'phase1_process') and self.phase1_process:
            print(f"🚀 [PRE-WARM] Phase 1 already running for {self.chat_id}. Skipping.")
            return
        
        self.phase1_ready = asyncio.Event()
        self.phase1_mobile = mobile
        
        global _running_loop
        if _running_loop:
            self.phase1_task = _running_loop.create_task(self._early_phase1_loop(mobile))
        else:
            print("⚠️ [PRE-WARM] Global event loop not set. Cannot spawn Phase 1 early.")

    async def _early_phase1_loop(self, mobile):
        try:
            print(f"🚀 [PRE-WARM] Spawning early Phase 1 subprocess for mobile: {mobile}...")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            get_eid_script = os.path.join(script_dir, 'retrive-eid.py')
            
            # Spawn retrive-eid.py with WAIT_INPUT placeholders
            self.phase1_process = await asyncio.create_subprocess_exec(
                sys.executable, '-u', get_eid_script, "WAIT_INPUT", "WAIT_INPUT", mobile,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Read stdout line-by-line until we hit the waiting print
            while True:
                line_bytes = await self.phase1_process.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode('utf-8', errors='ignore').strip()
                print(f"[get_eid prewarm {self.chat_id}] {line}")
                
                if "🔑 WAITING_FOR_NAME_DOB" in line:
                    print(f"🔑 [PRE-WARM] Early Phase 1 ready and blocking on stdin for {self.chat_id}.")
                    self.phase1_ready.set()
                    break
        except Exception as e:
            print(f"⚠️ [PRE-WARM] Error in early Phase 1 loop: {e}")
            if hasattr(self, 'phase1_process') and self.phase1_process:
                try: self.phase1_process.terminate()
                except: pass
                self.phase1_process = None



    async def wait_for_input(self, chat_id, prompt_type, timeout=300):
        str_chat_id = str(chat_id)
        
        # Check if there is a buffered input from the race window
        if str_chat_id in buffered_inputs:
            val = buffered_inputs.pop(str_chat_id)
            if val == '__CANCEL__':
                raise Exception("Process cancelled by user.")
            return val
            
        user_page_registry[str_chat_id] = {'type': prompt_type, 'value': None}
        try:
            for _ in range(timeout):
                # Also check if a buffered input arrived during the wait loop
                if str_chat_id in buffered_inputs:
                    val = buffered_inputs.pop(str_chat_id)
                    if val == '__CANCEL__':
                        raise Exception("Process cancelled by user.")
                    return val
                    
                if user_page_registry.get(str_chat_id) and user_page_registry[str_chat_id]['value'] is not None:
                    val = user_page_registry[str_chat_id]['value']
                    user_page_registry.pop(str_chat_id, None)
                    if val == '__CANCEL__':
                        raise Exception("Process cancelled by user.")
                    return val
                await asyncio.sleep(1)
            raise Exception(f"Timeout waiting for {prompt_type}")
        finally:
            user_page_registry.pop(str_chat_id, None)




    async def run_flow(self, chat_id, name, mobile, dob, user_info=None):
        self.start_time = time.time()
        self.start_preloader(f"📱 <b>STEP 3/4: EID Retrieval</b>\n\n⏳ <b>Retrieving EID details...</b>\n📱 <b>Target Mobile:</b> <code>{mobile}</code>")
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        get_eid_script = os.path.join(script_dir, 'retrive-eid.py')
        
        # Pass DD-MM-YYYY format directly to retrive-eid.py API script
        formatted_dob_iso = dob
        
        found_id = None
        process = None
        use_prewarmed = False
        if hasattr(self, 'phase1_process') and self.phase1_process:
            if getattr(self, 'phase1_mobile', None) == mobile and self.phase1_process.returncode is None:
                use_prewarmed = True

        captured_real_name = name # Fallback to input name
        try:
            if use_prewarmed:
                self.update_status("🔍 <b>PHASE 1: Retrieving ID...</b>\n⚡ <i>Using pre-warmed EID retrieval browser...</i>")
                try:
                    # Wait up to 15 seconds for the prewarm process to be ready
                    await asyncio.wait_for(self.phase1_ready.wait(), timeout=15.0)
                except asyncio.TimeoutError:
                    print("⚠️ [PRE-WARM] Timeout waiting for early Phase 1 to be ready. Falling back to fresh spawn.")
                    use_prewarmed = False

            if use_prewarmed and self.phase1_process and self.phase1_process.returncode is None:
                process = self.phase1_process
                print(f"🚀 [ENGINE] Writing credentials to pre-warmed process: {name}|{formatted_dob_iso}")
                process.stdin.write(f"{name}|{formatted_dob_iso}\n".encode('utf-8'))
                await process.stdin.drain()
            else:
                # Fall back to fresh spawn
                if hasattr(self, 'phase1_process') and self.phase1_process:
                    try: self.phase1_process.terminate()
                    except: pass
                    self.phase1_process = None
                
                print(f"🚀 [ENGINE] Starting fresh Aadhaar Retrieval for {name} ({formatted_dob_iso})...")
                process = await asyncio.create_subprocess_exec(
                    sys.executable, '-u', get_eid_script, name, str(formatted_dob_iso), mobile,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            
            # Read stdout dynamically line-by-line
            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode('utf-8', errors='ignore').strip()
                print(f"[get_eid] {line}")  # Log subprocess actions to the bot terminal
                
                # Intercept prefix rotation candidate to show live search progress
                if "Trying name payload:" in line:
                    self.preloader_base_text = (
                        f"📱 <b>STEP 3/4: EID Retrieval</b>\n\n"
                        f"🔍 <b>Searching database...</b>\n\n"
                        f"📱 <b>Target Mobile:</b> <code>{mobile}</code>"
                    )

                # Detect navigation retries and update status
                if "Navigation attempt" in line:
                    self.update_status(f"⚠️ <b>Portal response slow!</b> {escape_html(line)}. Kripya wait karein...")

                # Experiencing Technical Difficulties / Rate Limit detection
                if "LIMIT CROSSED" in line:
                    self.update_status("🛑 <b>LIMIT CROSSED!</b> Server has rate-limited this number or is experiencing overload. Please try again later.")
                    raise Exception("Technical difficulties / Rate limit reached. Limit crossed, try again later.")
                
                # Network Timeout detection
                if "NETWORK ERROR" in line:
                    self.update_status("🛑 <b>NETWORK ERROR!</b> Internet connection is extremely slow or gateway server is down. Please try again.")
                    raise Exception("Network issue / slow portal response.")
                
                # Successful OTP Triggered notification
                if "OTP Sent Successfully" in line:
                    self.stop_preloader()
                    otp1_card = get_ui_card(
                        step_num="3",
                        title="OTP 1 Verification",
                        description="🚀 <b>OTP 1 Sent Successfully!</b>\n👇 Kripya niche chat me <b>OTP</b> type karein:",
                        target=mobile
                    )
                    self.update_status(otp1_card)
                
                # Manual Captcha interceptor
                if line.startswith("🔑 MANUAL CAPTCHA REQUIRED |"):
                    b64_img = line.split("🔑 MANUAL CAPTCHA REQUIRED |")[1].strip()
                    self.stop_preloader()
                    
                    # Save temporary image file
                    temp_captcha_path = os.path.join(script_dir, f"temp_captcha_p1_{chat_id}.png")
                    with open(temp_captcha_path, "wb") as f_cap:
                        f_cap.write(base64.b64decode(b64_img.encode()))
                        
                    # Send image to Telegram user
                    with open(temp_captcha_path, "rb") as f_photo:
                        photo_msg = self.bot.send_photo(
                            chat_id, f_photo, 
                            caption="⚠️ <b>Auto-Captcha solve failed!</b>\n👇 Kripya image me dikh raha captcha code manually type karein:",
                            parse_mode='HTML'
                        )
                        try:
                            if photo_msg and int(chat_id) < 0:
                                self.temp_msg_ids.append(photo_msg.message_id)
                        except: pass
                    
                    # Wait for user input
                    user_captcha_val = await self.wait_for_input(chat_id, 'CAPTCHA')
                    self.start_preloader(f"📱 <b>STEP 3/4: EID Retrieval</b>\n\n⏳ <b>Submitting Captcha...</b>\n📱 <b>Target Mobile:</b> <code>{mobile}</code>")
                    
                    # Delete temp photo from disk
                    try:
                        os.remove(temp_captcha_path)
                    except: pass
                    
                    # Feed the typed captcha to the process stdin
                    process.stdin.write(f"{user_captcha_val}\n".encode())
                    await process.stdin.drain()

                # Prompt the Telegram user for OTP input and feed it to stdin
                if "ENTER THE OTP RECEIVED ON YOUR REGISTERED MOBILE" in line:
                    res_otp = await self.wait_for_input(chat_id, 'OTP')
                    self.refresh_status_card(f"📱 <b>STEP 3/4: OTP 1 Verification</b>\n\n⏳ <b>Submitting OTP 1...</b>\n📱 <b>Target Mobile:</b> <code>{mobile}</code>")
                    self.start_preloader(f"📱 <b>STEP 3/4: OTP 1 Verification</b>\n\n⏳ <b>Submitting OTP 1...</b>\n📱 <b>Target Mobile:</b> <code>{mobile}</code>")
                    process.stdin.write(f"{res_otp}\n".encode())
                    await process.stdin.drain()
                
                # Retrieve dynamic EID/UID capture
                if "CAPTURED ID SUCCESSFULLY:" in line:
                    found_id = line.split("CAPTURED ID SUCCESSFULLY:")[1].strip()
                    found_id = re.sub(r'[^a-zA-Z0-9]', '', found_id)  # Preserve S-prefix for SIDs/EIDs
                    
                if "CAPTURED NAME SUCCESSFULLY:" in line:
                    captured_real_name = line.split("CAPTURED NAME SUCCESSFULLY:")[1].strip()
            
            await process.wait()
            
            if not found_id:
                # Read stderr for traceback/error parsing
                stderr_bytes = await process.stderr.read()
                stderr_str = stderr_bytes.decode('utf-8', errors='ignore').strip()
                if stderr_str:
                    print(f"[get_eid error] {stderr_str}")
                    if "An error occurred:" in stderr_str:
                        err_msg = stderr_str.split("An error occurred:")[1].strip()
                        raise Exception(err_msg)
                    if "You have entered an invalid Captcha" in stderr_str:
                        raise Exception("Invalid Captcha! Please try again.")
                    if "experiencing technical difficulties" in stderr_str.lower():
                        raise Exception("Technical difficulties / Rate limit reached. Limit crossed, try again later.")
                    last_err = [l for l in stderr_str.splitlines() if l.strip()][-1]
                    raise Exception(last_err)
                raise Exception("Aadhaar details galat hain ya portal response match nahi ho raha.")
                
        except Exception as e:
            self.stop_preloader()
            if process:
                try:
                    process.terminate()
                except:
                    pass
            raise e
            
        if found_id:
            self.stop_preloader()
            await self.run_uidai_phase(chat_id, found_id, captured_real_name, mobile, user_info=user_info)



    async def run_uidai_phase(self, chat_id, eid, name, mobile, user_info=None):
        self.start_preloader(f"📱 <b>STEP 4/4: Aadhaar Download</b>\n\n⏳ <b>Fetching Aadhaar PDF...</b>\n📱 <b>Target Mobile:</b> <code>{mobile}</code>")
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        download_script = os.path.join(script_dir, 'aadhar-downlaod.py')
        
        max_retries = 3
        current_retry = 0
        while current_retry < max_retries:
            process = None
            try:
                print(f"🚀 [ENGINE] Starting Aadhaar Download subprocess for EID {eid}...")
                process = await asyncio.create_subprocess_exec(
                    sys.executable, '-u', download_script, str(eid), str(chat_id),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Read stdout dynamically line-by-line
                while True:
                    line_bytes = await process.stdout.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode('utf-8', errors='ignore').strip()
                    print(f"[aadhar-downlaod] {line}")
                    
                    # Decoded Captcha / Captcha Solve status
                    if "Decoded Captcha:" in line:
                        solved_cap = line.split("Decoded Captcha:")[1].strip()
                        self.update_status(f"🧩 <b>Captcha Solved:</b> <code>{solved_cap}</code>. Requesting OTP...")
                    
                    # Successful OTP Triggered notification
                    if "✅ OTP Sent Successfully!" in line:
                        self.stop_preloader()
                        otp2_card = get_ui_card(
                            step_num="4",
                            title="OTP 2 Verification",
                            description="✅ <b>OTP 2 Sent Successfully!</b>\n👇 Kripya niche chat me <b>OTP</b> type karein:",
                            target=mobile
                        )
                        self.update_status(otp2_card)
                    
                    # Manual Captcha interceptor
                    if line.startswith("🔑 MANUAL CAPTCHA REQUIRED |"):
                        b64_img = line.split("🔑 MANUAL CAPTCHA REQUIRED |")[1].strip()
                        self.stop_preloader()
                        
                        # Save temporary image file
                        temp_captcha_path = os.path.join(script_dir, f"temp_captcha_p2_{chat_id}.png")
                        with open(temp_captcha_path, "wb") as f_cap:
                            f_cap.write(base64.b64decode(b64_img.encode()))
                            
                        # Send image to Telegram user
                        with open(temp_captcha_path, "rb") as f_photo:
                            photo_msg = self.bot.send_photo(
                                chat_id, f_photo, 
                                caption="⚠️ <b>Auto-Captcha solve failed!</b>\n👇 Kripya image me dikh raha captcha code manually type karein:",
                                parse_mode='HTML'
                            )
                            try:
                                if photo_msg and int(chat_id) < 0:
                                    self.temp_msg_ids.append(photo_msg.message_id)
                            except: pass
                        
                        # Wait for user input
                        user_captcha_val = await self.wait_for_input(chat_id, 'CAPTCHA')
                        self.start_preloader(f"📱 <b>STEP 4/4: Aadhaar Download</b>\n\n⏳ <b>Submitting Captcha...</b>\n📱 <b>Target Mobile:</b> <code>{mobile}</code>")
                        
                        # Delete temp photo from disk
                        try:
                            os.remove(temp_captcha_path)
                        except: pass
                        
                        # Feed the typed captcha to the process stdin
                        process.stdin.write(f"{user_captcha_val}\n".encode())
                        await process.stdin.drain()

                    if "ENTER THE OTP RECEIVED ON YOUR REGISTERED MOBILE" in line:
                        res_otp = await self.wait_for_input(chat_id, 'OTP')
                        self.refresh_status_card(f"📱 <b>STEP 4/4: OTP 2 Verification</b>\n\n⏳ <b>Submitting OTP 2...</b>\n📱 <b>Target Mobile:</b> <code>{mobile}</code>")
                        self.start_preloader(f"📱 <b>STEP 4/4: OTP 2 Verification</b>\n\n⏳ <b>Submitting OTP 2...</b>\n📱 <b>Target Mobile:</b> <code>{mobile}</code>")
                        process.stdin.write(f"{res_otp}\n".encode())
                        await process.stdin.drain()
                        self.start_preloader(f"📱 <b>STEP 4/4: Aadhaar Download</b>\n\n📥 <b>Downloading File...</b>\n📱 <b>Target Mobile:</b> <code>{mobile}</code>")

                await process.wait()
                
                # Verify that download was indeed successful by checking file existence
                file_path = os.path.join(CRACKED_DIR, f"Aadhaar_{chat_id}.pdf")
                if os.path.exists(file_path):
                    await self.process_cracked_pdf(chat_id, file_path, name, mobile, eid=eid, user_info=user_info)
                    return
                else:
                    # Read stderr for error message
                    stderr_bytes = await process.stderr.read()
                    stderr_str = stderr_bytes.decode('utf-8', errors='ignore').strip()
                    if stderr_str:
                        print(f"[aadhar-downlaod error] {stderr_str}")
                        if "An error occurred:" in stderr_str:
                            err_msg = stderr_str.split("An error occurred:")[1].strip()
                            raise Exception(err_msg)
                        else:
                            last_err = [l for l in stderr_str.splitlines() if l.strip()][-1]
                            raise Exception(last_err)
                    raise Exception("Aadhaar download failed. EID details incorrect or invalid OTP.")
            except Exception as e:
                self.stop_preloader()
                if process:
                    try: process.terminate()
                    except: pass
                
                err_msg = str(e)
                if "technical difficulties" in err_msg.lower():
                    raise e
                is_otp_error = "invalid otp" in err_msg.lower() or "incorrect otp" in err_msg.lower()
                
                current_retry += 1
                if current_retry < max_retries:
                    if is_otp_error:
                        self.update_status("❌ <b>OTP Galat Hai / Session Expired!</b>\n🔄 <i>Phir se OTP send kiya jaa raha hai, kripya wait karein...</i>")
                    else:
                        self.update_status(f"⚠️ <b>Registry Phase Error:</b> {escape_html(str(e))}\n🔄 <i>Retrying...</i>")
                    await asyncio.sleep(2)
                else:
                    if is_otp_error:
                        raise Exception("❌ Invalid OTP. Max retries exceeded.")
                    else:
                        raise Exception(f"Registry Phase Failed: {e}")

    async def process_cracked_pdf(self, chat_id, file_path, name, mobile, eid=None, user_info=None):
        self.start_preloader("🔓 <b>File Downloaded!</b> Unlocking PDF...")
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            proc_script = os.path.join(script_dir, 'pdf_processor.py')
            # Always recreate the output dir in case user accidentally deleted it
            os.makedirs(CRACKED_DIR, exist_ok=True)
            process = await asyncio.create_subprocess_exec(
                sys.executable, proc_script, file_path, name, CRACKED_DIR, str(chat_id), 'True',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode('utf-8', errors='ignore')
            stderr_str = stderr.decode('utf-8', errors='ignore').strip()

            # Log full output for debugging
            if stdout_str.strip():
                print(f"[pdf_processor stdout] {stdout_str.strip()}")
            if stderr_str:
                print(f"[pdf_processor stderr] {stderr_str}")

            success_line = None
            uncracked_line = None
            error_line = None

            for line in stdout_str.split('\n'):
                line = line.strip()
                if line.startswith('SUCCESS|'):
                    success_line = line
                    break
                if line.startswith('UNCRACKED|'):
                    uncracked_line = line
                    break
                if line.startswith('ERROR|'):
                    error_line = line[6:]  # Strip "ERROR|" prefix

            if success_line:
                self.stop_preloader()
                # Use maxsplit=5 so Aadhaar UIDs with spaces don't break the split
                parts = success_line.split('|', 5)
                if len(parts) < 6:
                    raise Exception("PDF processor returned malformed SUCCESS line.")
                _, uid, pdf_out, front, back, password = parts

                time_str = "<b>N/A</b>"
                if hasattr(self, 'start_time') and self.start_time:
                    elapsed_sec = int(time.time() - self.start_time)
                    m = elapsed_sec // 60
                    s = elapsed_sec % 60
                    if m > 0:
                        time_str = f"<b>{m} min {s} sec</b>"
                    else:
                        time_str = f"<b>{s} sec</b>"

                success_text = (
                    f"🎉 <b>Success! Aadhaar Cracked.</b>\n\n"
                    f"👤 <b>Name:</b> <code>{name}</code>\n"
                    f"🆔 <b>EID:</b> <code>{eid or 'N/A'}</code>\n"
                    f"🔢 <b>Aadhaar Number:</b> <code>{uid}</code>\n"
                    f"🔑 <b>Password:</b> <code>{password}</code>\n\n"
                    f"⏱️ <b>Time Taken:</b> {time_str}"
                )
                self.bot.send_message(chat_id, success_text, parse_mode='HTML')
                
                try:
                    stats_manager.record_success(chat_id, user_info, name, mobile, uid, password, eid=eid)
                except Exception as se:
                    print(f"⚠️ [STATS] Failed to record success: {se}")

                # Save a permanent copy of the cracked Aadhaar PDF in the cracked_aadhar folder
                try:
                    import shutil
                    safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
                    safe_uid = uid.replace(' ', '')
                    permanent_pdf_name = f"{safe_name}_{safe_uid}.pdf"
                    permanent_pdf_path = os.path.join(CRACKED_DIR, permanent_pdf_name)
                    shutil.copy(pdf_out, permanent_pdf_path)
                    print(f"💾 [SAVED PDF] Saved permanent decrypted PDF to: {permanent_pdf_path}")
                except Exception as e_copy:
                    print(f"⚠️ [SAVED PDF] Failed to save permanent PDF copy: {e_copy}")

                # Update status card to indicate file transmission status
                self.update_status("📤 <b>Sending Aadhaar files...</b>")
                
                # Send the files in separate try-except blocks to prevent failure of one from losing others
                try:
                    if os.path.exists(front):
                        with open(front, 'rb') as f:
                            self.bot.send_photo(chat_id, f, caption="🖼️ <b>Aadhaar Front</b>", parse_mode='HTML')
                    else:
                        print(f"⚠️ Front image file not found: {front}")
                except Exception as e_front:
                    print(f"⚠️ Failed to send Front photo: {e_front}")
                    try:
                        self.bot.send_message(chat_id, f"⚠️ <b>Front Photo Send Failed:</b> {escape_html(str(e_front))}", parse_mode='HTML')
                    except: pass
                
                try:
                    if os.path.exists(back):
                        with open(back, 'rb') as f:
                            self.bot.send_photo(chat_id, f, caption="🖼️ <b>Aadhaar Back</b>", parse_mode='HTML')
                    else:
                        print(f"⚠️ Back image file not found: {back}")
                except Exception as e_back:
                    print(f"⚠️ Failed to send Back photo: {e_back}")
                    try:
                        self.bot.send_message(chat_id, f"⚠️ <b>Back Photo Send Failed:</b> {escape_html(str(e_back))}", parse_mode='HTML')
                    except: pass
                
                try:
                    if os.path.exists(pdf_out):
                        with open(pdf_out, 'rb') as f:
                            self.bot.send_document(chat_id, f, caption="📄 <b>Aadhaar PDF (Unlocked)</b>")
                    else:
                        print(f"⚠️ Unlocked PDF file not found: {pdf_out}")
                except Exception as e_pdf:
                    print(f"⚠️ Failed to send PDF: {e_pdf}")
                    try:
                        self.bot.send_message(chat_id, f"⚠️ <b>Aadhaar PDF Send Failed:</b> {escape_html(str(e_pdf))}", parse_mode='HTML')
                    except: pass

                # Finalize status card update
                self.update_status(f"✅ <b>Process Completed!</b>\nAadhaar data has been sent above.")

                # Cleanup all temporary files to save disk space and protect privacy
                for temp_f in [front, back, pdf_out, file_path]:
                    if temp_f and os.path.exists(temp_f):
                        try: os.remove(temp_f)
                        except: pass
                return

            if uncracked_line:
                self.stop_preloader()
                parts = uncracked_line.split('|', 1)
                locked_pdf_path = parts[1] if len(parts) > 1 else file_path

                time_str = "<b>N/A</b>"
                if hasattr(self, 'start_time') and self.start_time:
                    elapsed_sec = int(time.time() - self.start_time)
                    m = elapsed_sec // 60
                    s = elapsed_sec % 60
                    if m > 0:
                        time_str = f"<b>{m} min {s} sec</b>"
                    else:
                        time_str = f"<b>{s} sec</b>"

                uncracked_text = (
                    f"⚠️ <b>Aadhaar Crack Failed!</b>\n\n"
                    f"👤 <b>Name:</b> <code>{name}</code>\n"
                    f"🆔 <b>EID:</b> <code>{eid or 'N/A'}</code>\n"
                    f"🔑 <b>Password:</b> <code>Not Found (Could not crack)</code>\n\n"
                    f"ℹ️ <i>Bot isko crack nahi kar paya. Hum aapko original locked PDF send kar rahe hain. Aap ise manual password (Name ke first 4 capital letters + DOB Year) se open kar sakte hain.</i>\n\n"
                    f"⏱️ <b>Time Taken:</b> {time_str}"
                )
                self.bot.send_message(chat_id, uncracked_text, parse_mode='HTML')

                try:
                    stats_manager.record_failure()
                except Exception as se:
                    print(f"⚠️ [STATS] Failed to record failure: {se}")

                self.update_status("📤 <b>Sending Locked Aadhaar PDF...</b>")

                try:
                    if os.path.exists(locked_pdf_path):
                        with open(locked_pdf_path, 'rb') as f:
                            self.bot.send_document(chat_id, f, caption="📄 <b>Aadhaar PDF (Locked)</b>")
                    else:
                        print(f"⚠️ Locked PDF file not found: {locked_pdf_path}")
                except Exception as e_pdf:
                    print(f"⚠️ Failed to send PDF: {e_pdf}")
                    try:
                        self.bot.send_message(chat_id, f"⚠️ <b>Aadhaar PDF Send Failed:</b> {escape_html(str(e_pdf))}", parse_mode='HTML')
                    except: pass

                self.update_status(f"✅ <b>Process Completed!</b>\nLocked Aadhaar PDF has been sent above.")

                if os.path.exists(file_path):
                    try: os.remove(file_path)
                    except: pass
                return

            # No success — surface the real error
            if error_line:
                raise Exception(f"PDF Error: {error_line}")
            elif stderr_str:
                # Grab only the last meaningful line from stderr traceback
                last_err = [l for l in stderr_str.splitlines() if l.strip()][-1] if stderr_str else "Unknown error"
                raise Exception(f"PDF Processor crashed: {last_err}")
            else:
                raise Exception("PDF Cracking failed — password not found or PDF is unreadable.")

        except Exception as e:
            self.stop_preloader()
            self.update_status(f"❌ <b>PDF Crack Error:</b> {escape_html(str(e))}")


async def execute_task(bot, chat_id, name, mobile, dob, user_info=None):
    str_chat_id = str(chat_id)
    # Check if already processing a task
    if str_chat_id in active_tasks:
        bot.send_message(chat_id, "⏳ <b>Aapka task pehle se process ho raha hai.</b> Kripya wait karein.", parse_mode='HTML')
        return False

    # Enforce dynamic max concurrent active users
    max_concurrent = stats_manager.get_max_concurrent_tasks()
    if len(active_tasks) >= max_concurrent:
        bot.send_message(chat_id, f"⚠️ <b>Bot is overloaded!</b>\nAbhi ek saath {max_concurrent} users pehle se kaam kar rahe hain. Kripya thori der me try karein.", parse_mode='HTML')
        return False

    active_tasks.add(str_chat_id)
    if str_chat_id in active_engines:
        engine = active_engines[str_chat_id]
        print(f"🚀 [ENGINE] Reusing pre-warmed AadhaarEngine instance for {str_chat_id}")
    else:
        engine = AadhaarEngine(bot, chat_id=str_chat_id)
        active_engines[str_chat_id] = engine

    try:
        await engine.run_flow(chat_id, name, mobile, dob, user_info=user_info)
    except Exception as e:
        err_str = str(e)
        if "|||" in err_str:
            user_msg, real_msg = err_str.split("|||", 1)
            user_msg = user_msg.strip()
            real_msg = real_msg.strip()
        else:
            user_msg = err_str
            real_msg = err_str

        engine.update_status(f"❌ <b>Task Failed:</b> {escape_html(user_msg)}")
        try:
            is_user_error = any(x in user_msg.lower() for x in [
                "no record", "not found", "mismatch", "validation failed", 
                "invalid captcha", "incorrect otp", "invalid otp", 
                "incorrect details", "wrong captcha", "galat hain", 
                "match nahi", "incorrect", "invalid"
            ])
            if not is_user_error:
                stats_manager.record_failure()
            stats_manager.log_error(chat_id, user_info, f"Task Failed: {real_msg}")
        except Exception as se:
            print(f"⚠️ [STATS] Failed to record failure: {se}")
    finally:
        if str_chat_id in active_engines:
            del active_engines[str_chat_id]
        if str_chat_id in active_tasks:
            active_tasks.remove(str_chat_id)
        try:
            await engine.delete_temp_messages()
        except Exception as e:
            print(f"⚠️ [CLEANUP] Error during delete_temp_messages: {e}")
        await engine.close()
    return True

def prewarm_engine(bot, chat_id, mobile=None):
    str_chat_id = str(chat_id)
    if str_chat_id in active_engines:
        print(f"🚀 [PRE-WARM] Engine already active or pre-warmed for {str_chat_id}. Skipping.")
        engine = active_engines[str_chat_id]
        if mobile and (not hasattr(engine, 'phase1_process') or engine.phase1_process is None):
            engine.start_early_phase1(mobile)
        return
    
    engine = AadhaarEngine(bot, chat_id=str_chat_id)
    active_engines[str_chat_id] = engine
    
    global _running_loop
    if _running_loop and _running_loop.is_running():
        if mobile:
            engine.start_early_phase1(mobile)
    else:
        try:
            loop = asyncio.get_event_loop()
        except:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if mobile:
            loop.create_task(engine._early_phase1_loop(mobile))
