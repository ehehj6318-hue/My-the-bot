import os
import json
import datetime
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_FILE = os.path.join(BASE_DIR, "stats.json")
ERROR_LOG_FILE = os.path.join(BASE_DIR, "errors.log")
stats_lock = threading.RLock()
error_log_lock = threading.RLock()

def load_stats():
    """Thread-safe loading of stats.json. Returns default layout if file is missing/corrupted."""
    with stats_lock:
        if not os.path.exists(STATS_FILE) or os.path.getsize(STATS_FILE) == 0:
            return {
                "total_views": 0,
                "today_date": "",
                "today_views": 0,
                "success_count": 0,
                "fail_count": 0,
                "mode": "free",
                "default_credits": 3,
                "users": [],
                "cracked_history": [],
                "today_users": [],
                "cooldown_seconds": 60,
                "max_concurrent_tasks": 15
            }
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure all keys exist
                for key, default in [
                    ("total_views", 0),
                    ("today_date", ""),
                    ("today_views", 0),
                    ("success_count", 0),
                    ("fail_count", 0),
                    ("mode", "free"),
                    ("default_credits", 3),
                    ("users", []),
                    ("cracked_history", []),
                    ("today_users", []),
                    ("cooldown_seconds", 60),
                    ("max_concurrent_tasks", 15)
                ]:
                    if key not in data:
                        data[key] = default
                return data
        except Exception as e:
            print(f"⚠️ [STATS] Error loading stats.json: {e}")
            return {
                "total_views": 0,
                "today_date": "",
                "today_views": 0,
                "success_count": 0,
                "fail_count": 0,
                "mode": "free",
                "default_credits": 3,
                "users": [],
                "cracked_history": [],
                "today_users": [],
                "cooldown_seconds": 60,
                "max_concurrent_tasks": 15
            }

def save_stats(data):
    """Thread-safe atomic writing to stats.json."""
    with stats_lock:
        try:
            temp_file = STATS_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, STATS_FILE)
        except Exception as e:
            print(f"⚠️ [STATS] Error writing to stats.json: {e}")

def register_visit(chat_id, username=None, first_name=None):
    """Increments view counters and records user details for broadcasting."""
    with stats_lock:
        data = load_stats()
        today = datetime.date.today().isoformat()
        
        try:
            str_chat_id = int(chat_id)
        except:
            str_chat_id = chat_id
            
        # Initialize today_users if missing
        if "today_users" not in data:
            data["today_users"] = []
            
        # Today's views reset handler
        if data["today_date"] != today:
            data["today_date"] = today
            data["today_views"] = 1
            data["today_users"] = [str_chat_id]
            data["total_views"] += 1
        else:
            if str_chat_id not in data["today_users"]:
                data["today_users"].append(str_chat_id)
                data["today_views"] += 1
                data["total_views"] += 1
            
        # Migrate old integer list to list of dicts
        users_list = data.get("users", [])
        updated_users = []
        user_ids_seen = set()
        
        for u in users_list:
            if isinstance(u, dict):
                cid = u.get("chat_id")
                if cid not in user_ids_seen:
                    user_ids_seen.add(cid)
                    updated_users.append(u)
            else:
                try:
                    cid = int(u)
                    if cid not in user_ids_seen:
                        user_ids_seen.add(cid)
                        updated_users.append({
                            "chat_id": cid,
                            "first_name": "N/A",
                            "username": "N/A",
                            "joined": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                except:
                    pass
        
        # Check if user already registered
        existing_user = None
        for u in updated_users:
            if u["chat_id"] == str_chat_id:
                existing_user = u
                break
                
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if existing_user:
            # Update name/username if changed or not set
            if first_name and (existing_user.get("first_name") == "N/A" or existing_user.get("first_name") != first_name):
                existing_user["first_name"] = first_name
            if username and (existing_user.get("username") == "N/A" or existing_user.get("username") != username):
                existing_user["username"] = username
        else:
            # Create new user entry
            updated_users.append({
                "chat_id": str_chat_id,
                "first_name": first_name or "N/A",
                "username": username or "N/A",
                "joined": now_str,
                "credits": data.get("default_credits", 3)
            })
            
        data["users"] = updated_users
        save_stats(data)

def record_success(chat_id, user_info, name, mobile, uid, password, eid=None):
    """Increments success count and appends database record with user mappings and timestamps."""
    with stats_lock:
        data = load_stats()
        data["success_count"] += 1
        
        username = user_info.get("username", "N/A") if user_info else "N/A"
        first_name = user_info.get("first_name", "N/A") if user_info else "N/A"
        
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        record = {
            "timestamp": now,
            "chat_id": chat_id,
            "username": username,
            "first_name": first_name,
            "name": name,
            "mobile": mobile,
            "uid": uid,
            "password": password,
            "eid": eid or "N/A"
        }
        
        data["cracked_history"].append(record)
        save_stats(data)
        
        # Append to running permanent database text file log
        txt_file_path = os.path.join(BASE_DIR, "cracked_history.txt")
        try:
            with open(txt_file_path, "a", encoding="utf-8") as f:
                f.write("============================================================\n")
                f.write(f"{data['success_count']}. [Timestamp: {now}]\n")
                f.write(f"   👤 Telegram User: {first_name} (@{username}) [ID: {chat_id}]\n")
                f.write(f"   🆔 Holder Name: {name}\n")
                f.write(f"   📞 Mobile Number: {mobile}\n")
                f.write(f"   🆔 Enrollment ID (EID): {eid or 'N/A'}\n")
                f.write(f"   🔑 Cracked Aadhaar UID: {uid}\n")
                f.write(f"   🔓 PDF Password: {password}\n")
                f.write("============================================================\n\n")
        except Exception as e:
            print(f"⚠️ [STATS] Failed to write to cracked_history.txt: {e}")
        
        # Deduct credit if bot mode is paid
        try:
            deduct_user_credit(chat_id)
        except Exception as e:
            print(f"⚠️ [STATS] Error during success credit deduction: {e}")

def record_failure():
    """Increments failure counter."""
    with stats_lock:
        data = load_stats()
        data["fail_count"] += 1
        save_stats(data)

def get_stats_summary(active_user_states):
    """Compiles statistics into a premium, app-like visual dashboard for the Admin Telegram Panel."""
    data = load_stats()
    
    # Analyze active user states
    steps_breakdown = {}
    for uid, state_dict in active_user_states.items():
        step = state_dict.get("step", "IDLE")
        if step != "IDLE":
            steps_breakdown[step] = steps_breakdown.get(step, 0) + 1
            
    active_count = sum(steps_breakdown.values())
    
    active_details = ""
    if active_count > 0:
        active_details = ""
        for step, count in steps_breakdown.items():
            active_details += f"  ├─ <code>{step:<18}</code>: <b>{count} user(s)</b>\n"
    else:
        active_details = "  └─ <i>No users are running active tasks.</i>\n"

    mode = data.get("mode", "free").upper()
    def_credits = data.get("default_credits", 3)
    cooldown = data.get("cooldown_seconds", 60)
    max_concurrent = data.get("max_concurrent_tasks", 15)
    
    # Calculate success rate safely
    total_runs = data['success_count'] + data['fail_count']
    success_rate = 100
    if total_runs > 0:
        success_rate = int((data['success_count'] / total_runs) * 100)
        
    # Calculate user vs group splits
    total_users = 0
    total_groups = 0
    for u in data.get("users", []):
        if isinstance(u, dict):
            cid = u.get("chat_id", 0)
        else:
            try:
                cid = int(u)
            except:
                cid = 0
        if cid > 0:
            total_users += 1
        elif cid < 0:
            total_groups += 1
        
    summary = (
        "<b>ADMINISTRATION DASHBOARD v3.5</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ <b>SYSTEM CONFIGURATION:</b>\n"
        f"  ├─ Bot Mode:       <b>{mode} Mode</b>\n"
        f"  ├─ Def. Credits:   <code>{def_credits}</code>\n"
        f"  ├─ Global Cooldown: <code>{cooldown}s</code>\n"
        f"  └─ Max Concurrency: <code>{max_concurrent}</code>\n\n"
        "📊 <b>LIVE SYSTEM METRICS:</b>\n"
        f"  ├─ Total Views:      <code>{data['total_views']}</code>\n"
        f"  ├─ Today Views:      <code>{data['today_views']}</code>\n"
        f"  ├─ Total Users:      <code>{total_users}</code>\n"
        f"  ├─ Total Groups:     <code>{total_groups}</code>\n"
        f"  ├─ Registered All:   <code>{len(data['users'])}</code>\n"
        f"  └─ Success Rate:    <b>{success_rate}%</b> (<code>{data['success_count']} ✅</code> / <code>{data['fail_count']} ❌</code>)\n\n"
        f"👥 <b>ACTIVE ROOMS:</b> <code>{active_count} active</code>\n"
        f"{active_details}"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    return summary

def get_cracked_data_file_path():
    """Generates a text report of all cracked history database records with mapping & timestamps."""
    data = load_stats()
    report_path = os.path.join(BASE_DIR, "cracked_history_report.txt")
    
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("============================================================\n")
            f.write("🔒 CRACKED AADHAAR DATABASE REPORT\n")
            f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Successes: {data['success_count']}\n")
            f.write("============================================================\n\n")
            
            history = data.get("cracked_history", [])
            if not history:
                f.write("No cracked Aadhaar records found in database history yet.\n")
            else:
                for idx, record in enumerate(history, 1):
                    f.write("============================================================\n")
                    f.write(f"{idx}. [Timestamp: {record.get('timestamp', 'N/A')}]\n")
                    f.write(f"   👤 Telegram User: {record.get('first_name', 'N/A')} (@{record.get('username', 'N/A')}) [ID: {record.get('chat_id', 'N/A')}]\n")
                    f.write(f"   🆔 Holder Name: {record.get('name', 'N/A')}\n")
                    f.write(f"   📞 Mobile Number: {record.get('mobile', 'N/A')}\n")
                    f.write(f"   🆔 Enrollment ID (EID): {record.get('eid', 'N/A')}\n")
                    f.write(f"   🔑 Cracked Aadhaar UID: {record.get('uid', 'N/A')}\n")
                    f.write(f"   🔓 PDF Password: {record.get('password', 'N/A')}\n")
                    f.write("============================================================\n\n")
        return report_path
    except Exception as e:
        print(f"⚠️ [STATS] Failed to generate text database report: {e}")
        return None

def log_error(chat_id, user_info, error_msg):
    """Appends an error entry to errors.log with timestamps and user details."""
    with error_log_lock:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        username = user_info.get("username", "N/A") if user_info else "N/A"
        first_name = user_info.get("first_name", "N/A") if user_info else "N/A"
        
        entry = f"[{now}] User: {first_name} (@{username}) [ID: {chat_id}] | Error: {error_msg}\n"
        try:
            with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            print(f"⚠️ [STATS] Failed to write to errors.log: {e}")

def get_error_log_file_path():
    """Returns the path to errors.log if it exists and is not empty."""
    if os.path.exists(ERROR_LOG_FILE) and os.path.getsize(ERROR_LOG_FILE) > 0:
        return ERROR_LOG_FILE
    return None

# --- CREDIT & COOLDOWN MANAGEMENT SYSTEM ---

def get_bot_mode():
    """Returns the current bot mode ('free' or 'paid')."""
    with stats_lock:
        data = load_stats()
        return data.get("mode", "free")

def set_bot_mode(mode):
    """Sets the bot mode ('free' or 'paid')."""
    with stats_lock:
        data = load_stats()
        data["mode"] = mode
        save_stats(data)

def get_default_credits():
    """Returns the default credits count."""
    with stats_lock:
        data = load_stats()
        return data.get("default_credits", 3)

def set_default_credits(count):
    """Sets the default credits count."""
    with stats_lock:
        data = load_stats()
        data["default_credits"] = int(count)
        save_stats(data)

def get_user_credits(chat_id):
    """Returns the credits of the user. Defaults to default_credits."""
    with stats_lock:
        data = load_stats()
        try:
            str_chat_id = int(chat_id)
        except:
            str_chat_id = chat_id
            
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == str_chat_id:
                return u.get("credits", data.get("default_credits", 3))
        return data.get("default_credits", 3)

def add_user_credits(chat_id, amount):
    """Adds (or subtracts if negative) user credits. Returns the new credit balance."""
    with stats_lock:
        data = load_stats()
        try:
            str_chat_id = int(chat_id)
        except:
            str_chat_id = chat_id
            
        user_found = False
        new_balance = 0
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == str_chat_id:
                current_credits = u.get("credits", data.get("default_credits", 3))
                u["credits"] = max(0, current_credits + amount)
                new_balance = u["credits"]
                user_found = True
                break
                
        if not user_found:
            new_balance = max(0, data.get("default_credits", 3) + amount)
            data["users"].append({
                "chat_id": str_chat_id,
                "first_name": "N/A",
                "username": "N/A",
                "joined": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "credits": new_balance
            })
            
        save_stats(data)
        return new_balance

def deduct_user_credit(chat_id):
    """Deducts 1 credit from user if bot is in paid mode."""
    with stats_lock:
        data = load_stats()
        if data.get("mode", "free") != "paid":
            return
            
        try:
            str_chat_id = int(chat_id)
        except:
            str_chat_id = chat_id
            
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == str_chat_id:
                current_credits = u.get("credits", data.get("default_credits", 3))
                u["credits"] = max(0, current_credits - 1)
                break
        save_stats(data)

# In-memory global variables for cooldown tracking
last_global_run_time = 0

def check_global_cooldown():
    """Checks if the global cooldown is active. Returns (allowed, remaining_seconds)."""
    global last_global_run_time
    now = time.time()
    elapsed = now - last_global_run_time
    cooldown_limit = get_cooldown_seconds()
    if elapsed >= cooldown_limit:
        return True, 0
    else:
        return False, max(1, cooldown_limit - int(elapsed))

def update_global_run_time():
    """Updates the global cooldown timer to the current time."""
    global last_global_run_time
    last_global_run_time = time.time()

def get_cooldown_seconds():
    """Returns the configured global cooldown in seconds (default: 60)."""
    with stats_lock:
        data = load_stats()
        return data.get("cooldown_seconds", 60)

def set_cooldown_seconds(val):
    """Sets the global cooldown in seconds."""
    with stats_lock:
        data = load_stats()
        data["cooldown_seconds"] = int(val)
        save_stats(data)

def get_max_concurrent_tasks():
    """Returns the configured concurrency limit (default: 15)."""
    with stats_lock:
        data = load_stats()
        return data.get("max_concurrent_tasks", 15)

def set_max_concurrent_tasks(val):
    """Sets the concurrency limit."""
    with stats_lock:
        data = load_stats()
        data["max_concurrent_tasks"] = int(val)
        save_stats(data)

def is_user_registered(chat_id):
    """Checks if a user is already registered in our database."""
    with stats_lock:
        data = load_stats()
        try:
            str_chat_id = int(chat_id)
        except:
            str_chat_id = chat_id
        for u in data.get("users", []):
            if isinstance(u, dict) and u.get("chat_id") == str_chat_id:
                return True
        return False

def find_cracked_record(mobile):
    """Searches the cracked history database for a record matching the mobile number."""
    import re
    with stats_lock:
        data = load_stats()
        clean_mobile = re.sub(r'\D', '', str(mobile))
        for record in data.get("cracked_history", []):
            rec_mobile = re.sub(r'\D', '', str(record.get("mobile", "")))
            if rec_mobile == clean_mobile:
                return record
        return None
