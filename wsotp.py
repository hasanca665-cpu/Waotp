import os
import asyncio
import threading
import requests
import time
import json
import re
import logging
import aiohttp
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from datetime import datetime, timedelta
from telegram.error import BadRequest
from fastapi import FastAPI
import uvicorn
import random
from typing import Dict, List, Optional, Tuple
import jwt

# Configure logging to focus on errors only
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO,
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "7897173665:AAG1yIDgtbVv139I4-iZMxp2VYHRdkZH7Mo")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "5624278091"))
BASE_URL = os.environ.get("BASE_URL", "http://8.222.182.223:8081")

# Render-compatible port
RENDER_PORT = int(os.environ.get("PORT", 10000))

# File paths with Render.com compatibility
if 'RENDER' in os.environ:
    ACCOUNTS_FILE = "/tmp/accounts.json"
    STATS_FILE = "/tmp/stats.json"
    OTP_STATS_FILE = "/tmp/otp_stats.json"
    SETTINGS_FILE = "/tmp/settings.json"
else:
    ACCOUNTS_FILE = "accounts.json"
    STATS_FILE = "stats.json"
    OTP_STATS_FILE = "otp_stats.json"
    SETTINGS_FILE = "settings.json"

USD_TO_BDT = 124  # Exchange rate
MAX_PER_ACCOUNT = 5

# Status map
status_map = {
    0: "⚠️ Process Failed",
    1: "🟢 Success", 
    2: "🔵 In Progress",
    3: "⚠️ Try Again Later",
    4: "🚫 Not Register",
    7: "🚫 Ban Number",
    5: "🟡 Pending Verification",
    6: "🔴 Wrong OTP",
    8: "🟠 Limited",
    9: "🔶 Restricted", 
    10: "🟣 VIP Number",
    11: "⚠️ Add Again",
    12: "🟤 Temp Blocked",
    13: "Used Number",
    14: "🌀 Processing",
    15: "📞 Call Required",
    -1: "❌ Token Expired",
    -2: "❌ API Error",
    -3: "❌ No Data Found",
    16: "🚫 Already Exists"
}

# FastAPI for /ping endpoint
app = FastAPI()

@app.get("/")
async def root():
    return {"message": "🤖 Python Number Checker Bot is Running!", "status": "active", "timestamp": datetime.now().isoformat()}

@app.get("/ping")
async def ping():
    return {"message": "Bot is alive!", "status": "ok"}

@app.get("/health")
async def health():
    return {"status": "healthy", "bot": "online"}

# Enhanced keep-alive system for Render
async def keep_alive_enhanced():
    keep_alive_urls = [
        "https://waotp-dpqw.onrender.com",
        "https://autoping-1-ymen.onrender.com"
    ]
    
    while True:
        try:
            for url in keep_alive_urls:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=10) as response:
                            print(f"🔄 Keep-alive ping to {url}: Status {response.status}")
                            await asyncio.sleep(2)
                except Exception as e:
                    print(f"⚠️ Keep-alive ping failed for {url}: {e}")
            
            await asyncio.sleep(3 * 60)
            
        except Exception as e:
            print(f"❌ Keep-alive system error: {e}")
            await asyncio.sleep(3 * 60)

async def random_ping():
    while True:
        try:
            random_time = random.randint(2 * 60, 5 * 60)
            await asyncio.sleep(random_time)
            
            async with aiohttp.ClientSession() as session:
                async with session.get("https://webck-9utn.onrender.com", timeout=10) as response:
                    print(f"🎲 Random ping sent: Status {response.status}")
                    
        except Exception as e:
            print(f"⚠️ Random ping failed: {e}")

async def immediate_ping():
    await asyncio.sleep(30)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://webck-9utn.onrender.com", timeout=10) as response:
                print(f"🚀 Immediate startup ping: Status {response.status}")
    except Exception as e:
        print(f"⚠️ Immediate ping failed: {e}")

# tracking.json ফাইল অপারেশন
def load_tracking():
    try:
        with open("tracking.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "today_added" not in data or not isinstance(data["today_added"], dict):
                data["today_added"] = {}
            if "yesterday_added" not in data or not isinstance(data["yesterday_added"], dict):
                data["yesterday_added"] = {}
            if "today_success" not in data or not isinstance(data["today_success"], dict):
                data["today_success"] = {}
            if "yesterday_success" not in data or not isinstance(data["yesterday_success"], dict):
                data["yesterday_success"] = {}
            if "today_success_counts" not in data or not isinstance(data["today_success_counts"], dict):
                data["today_success_counts"] = {}
            if "daily_stats" not in data or not isinstance(data["daily_stats"], dict):
                data["daily_stats"] = {}
            return data
    except:
        return {
            "added_numbers": {},
            "success_numbers": {},
            "today_added": {},
            "yesterday_added": {},
            "today_success": {},
            "yesterday_success": {},
            "today_success_counts": {},
            "daily_stats": {},
            "last_reset": datetime.now().isoformat()
        }

def save_tracking(tracking):
    try:
        with open("tracking.json", 'w', encoding='utf-8') as f:
            json.dump(tracking, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Error saving tracking: {e}")

async def reset_daily_stats(context: CallbackContext):
    stats = load_stats()
    otp_stats = load_otp_stats()
    tracking = load_tracking()
    
    today_date = datetime.now().date().isoformat()
    
    # Save yesterday's data
    tracking["yesterday_added"] = tracking.get("today_added", {}).copy()
    
    if "daily_stats" not in tracking:
        tracking["daily_stats"] = {}
    
    today_success_by_user = tracking.get("today_success_counts", {}).copy()
    tracking["daily_stats"][today_date] = today_success_by_user
    
    # Reset today's data
    tracking["today_added"] = {}
    tracking["yesterday_success"] = tracking.get("today_success_counts", {}).copy()
    tracking["today_success"] = {}
    tracking["today_success_counts"] = {}
    tracking["last_reset"] = datetime.now().isoformat()
    
    # Reset stats
    stats["yesterday_checked"] = stats["today_checked"]
    stats["today_checked"] = 0
    stats["yesterday_deleted"] = stats["today_deleted"]
    stats["today_deleted"] = 0
    
    # Reset OTP stats
    otp_stats["yesterday_success"] = otp_stats["today_success"]
    otp_stats["today_success"] = 0
    
    for user_id_str in otp_stats.get("user_stats", {}):
        otp_stats["user_stats"][user_id_str]["yesterday_success"] = otp_stats["user_stats"][user_id_str].get("today_success", 0)
        otp_stats["user_stats"][user_id_str]["today_success"] = 0
    
    save_stats(stats)
    save_otp_stats(otp_stats)
    save_tracking(tracking)
    
    # Send reset notification to admin
    reset_message = "🔄 Daily Statistics Reset 🔄\n\n"
    reset_message += f"📅 Date: {datetime.now().strftime('%d %B %Y')}\n"
    reset_message += f"⏰ Reset Time: 4:00 PM (Bangladesh Time)\n\n"
    reset_message += "📊 Yesterday's Final Stats:\n"
    reset_message += f"• 🔵 In Progress: {sum(tracking['yesterday_added'].values())}\n"
    reset_message += f"• 🟢 Success: {sum(tracking['yesterday_success'].values())}\n"
    reset_message += f"• ✅ OTP Success: {otp_stats['yesterday_success']}\n"
    reset_message += f"• 📊 Checked: {stats['yesterday_checked']}\n\n"
    reset_message += "✅ All statistics have been reset for the new day!"
    
    try:
        await context.bot.send_message(ADMIN_ID, reset_message, parse_mode='none')
    except:
        pass
    
    print(f"✅ Daily tracking reset (BD Time 4PM) - Date: {today_date}")
    
# Enhanced file operations with error handling
def load_accounts():
    try:
        possible_paths = [
            ACCOUNTS_FILE,
            "accounts.json",
            "/tmp/accounts.json",
            "./accounts.json"
        ]
        
        for file_path in possible_paths:
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        print(f"✅ Loaded accounts from {file_path}")
                        return data
            except Exception as e:
                print(f"❌ Error loading from {file_path}: {e}")
                continue
        
        print("ℹ️ No accounts file found, starting fresh")
        initial_data = {
            str(ADMIN_ID): {
                "accounts": [],
                "selected_account_id": 1,
                "telegram_username": "",
                "last_active": datetime.now().isoformat()
            }
        }
        save_accounts(initial_data)
        return initial_data
        
    except Exception as e:
        print(f"❌ Critical error loading accounts: {e}")
        initial_data = {
            str(ADMIN_ID): {
                "accounts": [],
                "selected_account_id": 1,
                "telegram_username": "",
                "last_active": datetime.now().isoformat()
            }
        }
        return initial_data

def save_accounts(accounts):
    try:
        possible_paths = [
            ACCOUNTS_FILE,
            "accounts.json", 
            "/tmp/accounts.json"
        ]
        
        success = False
        for file_path in possible_paths:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(accounts, f, indent=4, ensure_ascii=False)
                print(f"✅ Saved accounts to {file_path}")
                success = True
                break
            except Exception as e:
                print(f"❌ Error saving to {file_path}: {e}")
                continue
        
        if not success:
            print("❌ Failed to save accounts to any location")
            
    except Exception as e:
        print(f"❌ Critical error saving accounts: {e}")

def load_stats():
    try:
        possible_paths = [STATS_FILE, "stats.json", "/tmp/stats.json", "./stats.json"]
        for file_path in possible_paths:
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            # Ensure all required keys exist
                            required_keys = [
                                "total_checked", "total_deleted", 
                                "today_checked", "today_deleted",
                                "yesterday_checked", "yesterday_deleted",
                                "last_reset"
                            ]
                            
                            for key in required_keys:
                                if key not in data:
                                    if key in ["total_checked", "today_checked", "yesterday_checked"]:
                                        data[key] = 0
                                    elif key in ["total_deleted", "today_deleted", "yesterday_deleted"]:
                                        data[key] = 0
                                    elif key == "last_reset":
                                        data[key] = datetime.now().isoformat()
                            
                            return data
                        else:
                            print(f"⚠️ Stats file contains {type(data)}, returning default")
                            return create_default_stats()
            except Exception as e:
                print(f"❌ Error loading from {file_path}: {e}")
                continue
        
        # If no file found, create default
        return create_default_stats()
        
    except Exception as e:
        print(f"❌ Error loading stats: {e}")
        return create_default_stats()

def create_default_stats():
    """Create default stats dictionary with all required keys"""
    return {
        "total_checked": 0, 
        "total_deleted": 0, 
        "today_checked": 0, 
        "today_deleted": 0,
        "yesterday_checked": 0,
        "yesterday_deleted": 0,
        "last_reset": datetime.now().isoformat()
    }

def save_stats(stats):
    try:
        # Ensure all required keys exist before saving
        required_keys = [
            "total_checked", "total_deleted", 
            "today_checked", "today_deleted",
            "yesterday_checked", "yesterday_deleted",
            "last_reset"
        ]
        
        for key in required_keys:
            if key not in stats:
                if key in ["total_checked", "today_checked", "yesterday_checked"]:
                    stats[key] = 0
                elif key in ["total_deleted", "today_deleted", "yesterday_deleted"]:
                    stats[key] = 0
                elif key == "last_reset":
                    stats[key] = datetime.now().isoformat()
        
        possible_paths = [STATS_FILE, "stats.json", "/tmp/stats.json"]
        for file_path in possible_paths:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(stats, f, indent=4, ensure_ascii=False)
                print(f"✅ Stats saved to {file_path}")
                break
            except Exception as e:
                print(f"❌ Error saving to {file_path}: {e}")
                continue
    except Exception as e:
        print(f"❌ Error saving stats: {e}")

def load_otp_stats():
    try:
        possible_paths = [OTP_STATS_FILE, "otp_stats.json", "/tmp/otp_stats.json", "./otp_stats.json"]
        for file_path in possible_paths:
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        print(f"✅ Loaded OTP stats from {file_path}")
                        return data
            except Exception as e:
                print(f"❌ Error loading from {file_path}: {e}")
                continue
        return {
            "total_success": 0,
            "today_success": 0,
            "yesterday_success": 0,
            "user_stats": {},
            "last_reset": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"❌ Error loading OTP stats: {e}")
        return {
            "total_success": 0,
            "today_success": 0,
            "yesterday_success": 0,
            "user_stats": {},
            "last_reset": datetime.now().isoformat()
        }

def save_otp_stats(otp_stats):
    try:
        possible_paths = [OTP_STATS_FILE, "otp_stats.json", "/tmp/otp_stats.json"]
        for file_path in possible_paths:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(otp_stats, f, indent=4, ensure_ascii=False)
                break
            except:
                continue
    except Exception as e:
        print(f"❌ Error saving OTP stats: {e}")

def load_settings():
    try:
        possible_paths = [SETTINGS_FILE, "settings.json", "/tmp/settings.json", "./settings.json"]
        for file_path in possible_paths:
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        print(f"✅ Loaded settings from {file_path}")
                        return data
            except Exception as e:
                print(f"❌ Error loading from {file_path}: {e}")
                continue
        default_settings = {
            "settlement_rate": 0.10,
            "last_updated": datetime.now().isoformat(),
            "updated_by": ADMIN_ID
        }
        save_settings(default_settings)
        return default_settings
    except Exception as e:
        print(f"❌ Error loading settings: {e}")
        default_settings = {
            "settlement_rate": 0.10,
            "last_updated": datetime.now().isoformat(),
            "updated_by": ADMIN_ID
        }
        return default_settings

def save_settings(settings):
    try:
        possible_paths = [SETTINGS_FILE, "settings.json", "/tmp/settings.json"]
        for file_path in possible_paths:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=4, ensure_ascii=False)
                break
            except:
                continue
    except Exception as e:
        print(f"❌ Error saving settings: {e}")

# Active OTP requests (in-memory only)
active_otp_requests = {}

# Async login - UPDATED VERSION
async def login_api_async(username, password):
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"account": username, "password": password, "identity": "Member"}
            
            print(f"🔄 Attempting login for: {username}")
            
            async with session.post(f"{BASE_URL}/user/login", json=payload, timeout=30) as response:
                response_text = await response.text()
                print(f"📥 Response status: {response.status}")
                
                if response.status == 200:
                    try:
                        data = await response.json(content_type=None)
                        
                        if data and isinstance(data, dict):
                            if "data" in data and "token" in data["data"]:
                                token = data["data"]["token"]
                                
                                try:
                                    decoded = jwt.decode(token, options={"verify_signature": False})
                                    api_user_id = decoded.get('id')
                                    nickname = decoded.get('nickname')
                                    
                                    print(f"✅ Login successful for {username}")
                                    print(f"📝 API User ID: {api_user_id}")
                                    print(f"👤 Nickname: {nickname}")
                                    
                                    return token, api_user_id, nickname
                                except Exception as jwt_error:
                                    print(f"⚠️ Could not decode token: {jwt_error}")
                                    return token, None, None
                            else:
                                print(f"❌ Token not found in response for {username}")
                                return None, None, None
                        else:
                            print(f"❌ Invalid response format for {username}")
                            return None, None, None
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON decode error for {username}: {e}")
                        print(f"❌ Raw response: {response_text[:200]}...")
                        return None, None, None
                else:
                    print(f"❌ Login failed: {username} - Status: {response.status}")
                    return None, None, None
    except asyncio.TimeoutError:
        print(f"❌ Login timeout for {username}")
        return None, None, None
    except Exception as e:
        print(f"❌ Login error for {username}: {type(e).__name__}: {e}")
        return None, None, None

def calculate_daily_stats():
    """Calculate daily statistics from tracking data"""
    tracking = load_tracking()
    stats = load_stats()
    
    today_date = datetime.now().date().isoformat()
    
    # Calculate totals
    total_in_progress = 0
    total_success = 0
    
    # Get counts from tracking
    if "today_added" in tracking:
        for user_id, count in tracking["today_added"].items():
            if isinstance(count, (int, float)):
                total_in_progress += count
    
    if "today_success_counts" in tracking:
        for user_id, count in tracking["today_success_counts"].items():
            if isinstance(count, (int, float)):
                total_success += count
    
    # Get active in-progress numbers from active_numbers
    active_in_progress = len(active_numbers)
    
    return {
        "date": today_date,
        "total_in_progress": total_in_progress,
        "active_in_progress": active_in_progress,
        "total_success": total_success,
        "total_checked": stats.get("today_checked", 0),
        "total_deleted": stats.get("today_deleted", 0)
    }

async def show_user_statistics(update: Update, context: CallbackContext):
    """Show individual user statistics"""
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    
    tracking = load_tracking()
    stats = load_stats()  # This will now work with the fixed function
    otp_stats = load_otp_stats()
    
    today_date = datetime.now().date().isoformat()
    
    # Get user-specific stats with default values
    user_in_progress = tracking.get("today_added", {}).get(user_id_str, 0)
    user_success = tracking.get("today_success_counts", {}).get(user_id_str, 0)
    
    # Get OTP stats with default values
    user_otp_stats = otp_stats.get("user_stats", {}).get(user_id_str, {})
    today_otp_success = user_otp_stats.get("today_success", 0)
    yesterday_otp_success = user_otp_stats.get("yesterday_success", 0)
    
    # Get account info
    accounts = load_accounts()
    user_data = accounts.get(user_id_str, {})
    user_accounts = user_data.get("accounts", []) if isinstance(user_data, dict) else []
    active_accounts = account_manager.get_user_active_accounts_count(user_id)
    remaining_checks = account_manager.get_user_remaining_checks(user_id)
    
    message = "📊 Your Daily Statistics 📊\n\n"
    
    message += f"📅 Date: {datetime.now().strftime('%d %B %Y')}\n"
    message += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')} (BD Time)\n"
    message += f"🔄 Next Reset: Today 4:00 PM (BD Time)\n\n"
    
    message += "👤 Account Information:\n"
    message += f"• 📱 Total Accounts: {len(user_accounts)}\n"
    message += f"• ✅ Active Login: {active_accounts}\n"
    message += f"• 🎯 Remaining Add: {remaining_checks}\n\n"
    
    message += "📈 Today's Performance:\n"
    message += f"• 📱Added Numbers: {user_in_progress}\n"
    message += f"• 🟢 Success Counts: {user_success}\n"
    message += f"• ✅ OTP Success: {today_otp_success}\n\n"
    
    
    message += "🔄 Auto Reset: Daily at 4:00 PM (Bangladesh Time)"
    
    await update.message.reply_text(message, parse_mode='none')

async def show_admin_statistics(update: Update, context: CallbackContext):
    """Show admin statistics with all users data"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
    
    processing_msg = await update.message.reply_text("🔄 Generating statistics report...")
    
    tracking = load_tracking()
    stats = load_stats()
    otp_stats = load_otp_stats()
    accounts = load_accounts()
    
    today_date = datetime.now().date().isoformat()
    today_display = datetime.now().strftime('%d %B %Y')
    
    # Calculate totals
    total_in_progress = 0
    total_success = 0
    total_users = 0
    
    # User-wise calculations
    user_stats = []
    
    for user_id_str, user_data in accounts.items():
        if user_id_str == str(ADMIN_ID):
            continue
        
        if isinstance(user_data, dict):
            user_accounts = user_data.get("accounts", [])
        else:
            user_accounts = []
        
        if not user_accounts:
            continue
        
        total_users += 1
        username = user_accounts[0].get('username', 'Unknown') if user_accounts else 'Unknown'
        
        # Get user stats
        user_in_progress = tracking.get("today_added", {}).get(user_id_str, 0)
        user_success = tracking.get("today_success_counts", {}).get(user_id_str, 0)
        user_otp_success = otp_stats.get("user_stats", {}).get(user_id_str, {}).get("today_success", 0)
        
        total_in_progress += user_in_progress
        total_success += user_success
        
        user_stats.append({
            'user_id': user_id_str,
            'username': username,
            'in_progress': user_in_progress,
            'success': user_success,
            'otp_success': user_otp_success,
            'accounts': len(user_accounts)
        })
    
    # Sort users by success count (descending)
    user_stats.sort(key=lambda x: x['success'], reverse=True)
    
    # Send summary first
    summary_message = "👑 ADMIN STATISTICS SUMMARY 👑\n\n"
    
    summary_message += f"📅 Date: {today_display}\n"
    summary_message += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')} (BD Time)\n"
    summary_message += f"🔄 Next Reset: Today 4:00 PM (BD Time)\n\n"
    
    summary_message += "📊 TODAY'S OVERVIEW:\n"
    summary_message += f"• 👥 Total Users: {total_users}\n"
    summary_message += f"• 🔵 Total In Progress: {total_in_progress}\n"
    summary_message += f"• 🟢 Total Success: {total_success}\n"
    summary_message += f"• ✅ Total OTP Success: {otp_stats.get('today_success', 0)}\n"
    summary_message += f"• 📊 Total Checked: {stats.get('today_checked', 0)}\n"
    summary_message += f"• 🗑️ Total Deleted: {stats.get('today_deleted', 0)}\n\n"
    
    summary_message += "📈 YESTERDAY'S SUMMARY:\n"
    summary_message += f"• 🟢 Success Counts: {otp_stats.get('yesterday_success', 0)}\n"
    summary_message += f"• 📊 Checked: {stats.get('yesterday_checked', 0)}\n\n"
    
    summary_message += "📌 Note: In Progress counts all numbers added today.\n"
    summary_message += "Success counts only unique successful numbers.\n"
    
    await processing_msg.edit_text(summary_message, parse_mode='none')
    
    # Send user details in chunks of 10
    users_per_message = 10
    total_chunks = (len(user_stats) + users_per_message - 1) // users_per_message
    
    for chunk_index in range(total_chunks):
        start_idx = chunk_index * users_per_message
        end_idx = min(start_idx + users_per_message, len(user_stats))
        chunk = user_stats[start_idx:end_idx]
        
        details_message = f"📋 USER STATISTICS - PART {chunk_index + 1}/{total_chunks} 📋\n\n"
        details_message += f"📅 Date: {today_display}\n\n"
        
        for i, user in enumerate(chunk, start=start_idx + 1):
            details_message += f"{i}. {user['username']} (ID: {user['user_id']})\n"
            details_message += f"   ├─ 📱 Accounts: {user['accounts']}\n"
            details_message += f"   ├─ 🔵 In Progress: {user['in_progress']}\n"
            details_message += f"   ├─ 🟢 Success: {user['success']}\n"
            details_message += f"   ├─ ✅ OTP Success: {user['otp_success']}\n"
            
            # Calculate success rate
            if user['in_progress'] > 0:
                success_rate = (user['success'] / user['in_progress']) * 100
                details_message += f"   └─ 📈 Success Rate: {success_rate:.1f}%\n"
            else:
                details_message += f"   └─ 📈 Success Rate: 0%\n"
            
            details_message += "\n"
        
        # Add chunk totals
        chunk_in_progress = sum(u['in_progress'] for u in chunk)
        chunk_success = sum(u['success'] for u in chunk)
        
        details_message += f"📊 Chunk {chunk_index + 1} Summary:\n"
        details_message += f"• 👥 Users: {len(chunk)}\n"
        details_message += f"• 🔵 In Progress: {chunk_in_progress}\n"
        details_message += f"• 🟢 Success: {chunk_success}\n"
        
        if chunk_in_progress > 0:
            chunk_success_rate = (chunk_success / chunk_in_progress) * 100
            details_message += f"• 📈 Success Rate: {chunk_success_rate:.1f}%\n"
        
        if chunk_index < total_chunks - 1:
            details_message += "\n⬇️ More users in next message..."
        
        try:
            await context.bot.send_message(
                ADMIN_ID,
                details_message,
                parse_mode='none'
            )
            await asyncio.sleep(1)
        except Exception as e:
            print(f"❌ Error sending statistics chunk {chunk_index + 1}: {e}")
    
    # Send final totals
    final_message = "🎯 FINAL DAILY SUMMARY 🎯\n\n"
    
    final_message += f"📅 Date: {today_display}\n"
    final_message += f"⏰ Report Time: {datetime.now().strftime('%H:%M:%S')}\n\n"
    
    final_message += "📊 TOTAL STATISTICS:\n"
    final_message += f"• 👥 Total Active Users: {total_users}\n"
    final_message += f"• 🔵 Total In Progress Numbers: {total_in_progress}\n"
    final_message += f"• 🟢 Total Success Counts: {total_success}\n"
    final_message += f"• ✅ Total OTP Success: {otp_stats.get('today_success', 0)}\n\n"
    
    # Calculate overall success rate
    if total_in_progress > 0:
        overall_success_rate = (total_success / total_in_progress) * 100
        final_message += f"📈 OVERALL SUCCESS RATE: {overall_success_rate:.1f}%\n\n"
    
    # Top performers
    if len(user_stats) >= 3:
        final_message += "🏆 TOP 3 PERFORMERS TODAY:\n"
        for i in range(min(3, len(user_stats))):
            user = user_stats[i]
            final_message += f"{i+1}. {user['username']} - {user['success']} success\n"
        final_message += "\n"
    
    final_message += "🔄 Statistics will reset at 4:00 PM (Bangladesh Time)\n"
    final_message += "✅ Report generation complete!"
    
    await context.bot.send_message(ADMIN_ID, final_message, parse_mode='none')

async def statistics_command(update: Update, context: CallbackContext):
    """Handle /statistics command for both users and admin"""
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        if context.args and context.args[0].lower() == 'all':
            await show_admin_statistics(update, context)
        else:
            # Admin sees both personal and option for all
            keyboard = [
                [InlineKeyboardButton("📊 My Statistics", callback_data="stats_personal")],
                [InlineKeyboardButton("👑 All Users Statistics", callback_data="stats_all")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "📊 Statistics Menu\n\n"
                "Choose what statistics you want to see:",
                reply_markup=reply_markup
            )
    else:
        await show_user_statistics(update, context)

async def handle_statistics_callback(update: Update, context: CallbackContext):
    """Handle statistics callback queries"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "stats_personal":
        await show_user_statistics_from_callback(query, context)
    elif data == "stats_all":
        await show_admin_statistics_from_callback(query, context)

async def show_user_statistics_from_callback(query, context):
    """Show user statistics from callback"""
    user_id = query.from_user.id
    
    tracking = load_tracking()
    stats = load_stats()
    otp_stats = load_otp_stats()
    
    user_id_str = str(user_id)
    today_date = datetime.now().date().isoformat()
    
    # Get user-specific stats
    user_in_progress = tracking.get("today_added", {}).get(user_id_str, 0)
    user_success = tracking.get("today_success_counts", {}).get(user_id_str, 0)
    
    # Get OTP stats
    user_otp_stats = otp_stats.get("user_stats", {}).get(user_id_str, {})
    today_otp_success = user_otp_stats.get("today_success", 0)
    yesterday_otp_success = user_otp_stats.get("yesterday_success", 0)
    
    # Get account info
    accounts = load_accounts()
    user_data = accounts.get(user_id_str, {})
    user_accounts = user_data.get("accounts", []) if isinstance(user_data, dict) else []
    active_accounts = account_manager.get_user_active_accounts_count(user_id)
    remaining_checks = account_manager.get_user_remaining_checks(user_id)
    
    message = "📊 Your Daily Statistics 📊\n\n"
    
    message += f"📅 Date: {datetime.now().strftime('%d %B %Y')}\n"
    message += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')} (BD Time)\n"
    message += f"🔄 Next Reset: Today 4:00 PM (BD Time)\n\n"
    
    message += "👤 Account Information:\n"
    message += f"• 📱 Total Accounts: {len(user_accounts)}\n"
    message += f"• ✅ Active Login: {active_accounts}\n"
    message += f"• 🎯 Remaining Add: {remaining_checks}\n\n"
    
    message += "📈 Today's Performance:\n"
    message += f"• 📱 Added Numbers: {user_in_progress}\n"
    message += f"• 🟢 Success Counts: {user_success}\n"
    message += f"• ✅ OTP Success: {today_otp_success}\n\n"
    
    
    message += "🔄 Auto Reset: Daily at 4:00 PM (Bangladesh Time)"
    
    await query.edit_message_text(message, parse_mode='none')

async def show_admin_statistics_from_callback(query, context):
    """Show admin statistics from callback"""
    await query.edit_message_text("🔄 Generating all users statistics report...")
    await show_admin_statistics_from_message(query, context)

async def show_admin_statistics_from_message(message_obj, context):
    """Show admin statistics from message object"""
    tracking = load_tracking()
    stats = load_stats()
    otp_stats = load_otp_stats()
    accounts = load_accounts()
    
    today_date = datetime.now().date().isoformat()
    today_display = datetime.now().strftime('%d %B %Y')
    
    # Calculate totals
    total_in_progress = 0
    total_success = 0
    total_users = 0
    
    # User-wise calculations
    user_stats = []
    
    for user_id_str, user_data in accounts.items():
        if user_id_str == str(ADMIN_ID):
            continue
        
        if isinstance(user_data, dict):
            user_accounts = user_data.get("accounts", [])
        else:
            user_accounts = []
        
        if not user_accounts:
            continue
        
        total_users += 1
        username = user_accounts[0].get('username', 'Unknown') if user_accounts else 'Unknown'
        
        # Get user stats
        user_in_progress = tracking.get("today_added", {}).get(user_id_str, 0)
        user_success = tracking.get("today_success_counts", {}).get(user_id_str, 0)
        user_otp_success = otp_stats.get("user_stats", {}).get(user_id_str, {}).get("today_success", 0)
        
        total_in_progress += user_in_progress
        total_success += user_success
        
        user_stats.append({
            'user_id': user_id_str,
            'username': username,
            'in_progress': user_in_progress,
            'success': user_success,
            'otp_success': user_otp_success,
            'accounts': len(user_accounts)
        })
    
    # Sort users by success count (descending)
    user_stats.sort(key=lambda x: x['success'], reverse=True)
    
    # Send summary
    summary_message = "👑 ADMIN STATISTICS SUMMARY 👑\n\n"
    
    summary_message += f"📅 Date: {today_display}\n"
    summary_message += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')} (BD Time)\n"
    summary_message += f"🔄 Next Reset: Today 4:00 PM (BD Time)\n\n"
    
    summary_message += "📊 TODAY'S OVERVIEW:\n"
    summary_message += f"• 👥 Total Users: {total_users}\n"
    summary_message += f"• 🔵 Total In Progress: {total_in_progress}\n"
    summary_message += f"• 🟢 Total Success: {total_success}\n"
    summary_message += f"• ✅ Total OTP Success: {otp_stats.get('today_success', 0)}\n"
    summary_message += f"• 📊 Total Checked: {stats.get('today_checked', 0)}\n"
    summary_message += f"• 🗑️ Total Deleted: {stats.get('today_deleted', 0)}\n\n"
    
    await message_obj.edit_message_text(summary_message, parse_mode='none')
    
    # Send user details in chunks of 10
    users_per_message = 10
    total_chunks = (len(user_stats) + users_per_message - 1) // users_per_message
    
    for chunk_index in range(total_chunks):
        start_idx = chunk_index * users_per_message
        end_idx = min(start_idx + users_per_message, len(user_stats))
        chunk = user_stats[start_idx:end_idx]
        
        details_message = f"📋 USER STATISTICS - PART {chunk_index + 1}/{total_chunks} 📋\n\n"
        details_message += f"📅 Date: {today_display}\n\n"
        
        for i, user in enumerate(chunk, start=start_idx + 1):
            details_message += f"{i}. {user['username']} (ID: {user['user_id']})\n"
            details_message += f"   ├─ 📱 Accounts: {user['accounts']}\n"
            details_message += f"   ├─ 🔵 In Progress: {user['in_progress']}\n"
            details_message += f"   ├─ 🟢 Success: {user['success']}\n"
            details_message += f"   ├─ ✅ OTP Success: {user['otp_success']}\n"
            
            if user['in_progress'] > 0:
                success_rate = (user['success'] / user['in_progress']) * 100
                details_message += f"   └─ 📈 Success Rate: {success_rate:.1f}%\n"
            else:
                details_message += f"   └─ 📈 Success Rate: 0%\n"
            
            details_message += "\n"
        
        chunk_in_progress = sum(u['in_progress'] for u in chunk)
        chunk_success = sum(u['success'] for u in chunk)
        
        details_message += f"📊 Chunk {chunk_index + 1} Summary:\n"
        details_message += f"• 👥 Users: {len(chunk)}\n"
        details_message += f"• 🔵 In Progress: {chunk_in_progress}\n"
        details_message += f"• 🟢 Success: {chunk_success}\n"
        
        if chunk_index < total_chunks - 1:
            details_message += "\n⬇️ More users in next message..."
        
        try:
            await context.bot.send_message(
                ADMIN_ID,
                details_message,
                parse_mode='none'
            )
            await asyncio.sleep(1)
        except Exception as e:
            print(f"❌ Error sending statistics chunk {chunk_index + 1}: {e}")
    
    # Send final totals
    final_message = "🎯 FINAL DAILY SUMMARY 🎯\n\n"
    
    final_message += f"📅 Date: {today_display}\n"
    final_message += f"⏰ Report Time: {datetime.now().strftime('%H:%M:%S')}\n\n"
    
    final_message += "📊 TOTAL STATISTICS:\n"
    final_message += f"• 👥 Total Active Users: {total_users}\n"
    final_message += f"• 🔵 Total In Progress Numbers: {total_in_progress}\n"
    final_message += f"• 🟢 Total Success Counts: {total_success}\n"
    final_message += f"• ✅ Total OTP Success: {otp_stats.get('today_success', 0)}\n\n"
    
    if total_in_progress > 0:
        overall_success_rate = (total_success / total_in_progress) * 100
        final_message += f"📈 OVERALL SUCCESS RATE: {overall_success_rate:.1f}%\n\n"
    
    if len(user_stats) >= 3:
        final_message += "🏆 TOP 3 PERFORMERS TODAY:\n"
        for i in range(min(3, len(user_stats))):
            user = user_stats[i]
            final_message += f"{i+1}. {user['username']} - {user['success']} success\n"
        final_message += "\n"
    
    final_message += "🔄 Statistics will reset at 4:00 PM (Bangladesh Time)\n"
    final_message += "✅ Report generation complete!"
    
    await context.bot.send_message(ADMIN_ID, final_message, parse_mode='none')

def extract_phone_numbers(text: str) -> List[Dict[str, str]]:
    """
    Extract phone numbers with country codes from text
    Returns list of dictionaries with 'cc' and 'phone' keys
    """
    all_numbers = []
    
    # Define common country codes (expanded list)
    # IMPORTANT: For USA/Canada, API needs "11" instead of "1"
    country_codes = {
        '1': '11',  # USA/Canada - FIXED: API requires "11"
        '7': 'RU/KZ',
        '20': 'EG',
        '27': 'ZA',
        # ... rest of the country codes remain same
    }
    
    # ১. প্রথমে + সহ নম্বর এক্সট্র্যাক্ট করা
    pattern_plus = r'\+\s*(\d{1,4})\s*([\d\s\-\.\(\)]+)'
    matches_plus = re.finditer(pattern_plus, text, re.IGNORECASE)
    
    for match in matches_plus:
        cc = match.group(1).strip()
        phone_part = match.group(2).strip()
        
        # Clean phone part - remove all non-digits
        phone_digits = re.sub(r'\D', '', phone_part)
        
        # SPECIAL FIX: USA/Canada এর জন্য cc = "11"
        if cc == '1':
            cc = '11'  # API requires "11" for USA/Canada
            print(f"✅ Converted USA/Canada CC from 1 to 11 for phone: {phone_digits}")
        
        # Check if CC is valid
        if cc in ['11', '7', '20', '27', '30', '31', '32', '33', '34', '36', '39', '40', 
                  '41', '43', '44', '45', '46', '47', '48', '49', '51', '52', '53', '54', 
                  '55', '56', '57', '58', '60', '61', '62', '63', '64', '65', '66', '81', 
                  '82', '84', '86', '90', '91', '92', '93', '94', '95', '98', '212', '213', 
                  '216', '218', '220', '221', '222', '223', '224', '225', '226', '227', 
                  '228', '229', '230', '231', '232', '233', '234', '235', '236', '237', 
                  '238', '239', '240', '241', '242', '243', '244', '245', '246', '247', 
                  '248', '249', '250', '251', '252', '253', '254', '255', '256', '257', 
                  '258', '260', '261', '262', '263', '264', '265', '266', '267', '268', 
                  '269', '290', '291', '297', '298', '299', '350', '351', '352', '353', 
                  '354', '355', '356', '357', '358', '359', '370', '371', '372', '373', 
                  '374', '375', '376', '377', '378', '379', '380', '381', '382', '383', 
                  '385', '386', '387', '389', '420', '421', '423', '500', '501', '502', 
                  '503', '504', '505', '506', '507', '508', '509', '590', '591', '592', 
                  '593', '594', '595', '596', '597', '598', '599', '670', '672', '673', 
                  '674', '675', '676', '677', '678', '679', '680', '681', '682', '683', 
                  '685', '686', '687', '688', '689', '690', '691', '692', '850', '852', 
                  '853', '855', '856', '880', '886', '960', '961', '962', '963', '964', 
                  '965', '966', '967', '968', '970', '971', '972', '973', '974', '975', 
                  '976', '977', '992', '993', '994', '995', '996', '998']:
            # Phone should have reasonable length (7-15 digits)
            if 7 <= len(phone_digits) <= 15:
                all_numbers.append({
                    'cc': cc,
                    'phone': phone_digits,
                    'source': 'plus_format'
                })
                print(f"✅ Extracted from + format: CC={cc}, Phone={phone_digits}")
    
    # ২. যদি + না থাকে, শুধু ডিজিট থাকে
    if not all_numbers:
        # Find all sequences of digits
        all_digits = re.findall(r'\d+', text)
        
        for digits in all_digits:
            # Check if this looks like a phone number with country code
            if len(digits) >= 10:  # Minimum for country code + phone
                found_cc = None
                found_phone = None
                
                # SPECIAL HANDLING FOR USA/CANADA
                # Check for USA/Canada pattern: starts with 1 followed by 10 digits
                if digits.startswith('1') and len(digits) == 11:
                    # USA/Canada: 1 followed by 10-digit phone
                    found_cc = '11'  # API requires "11"
                    found_phone = digits[1:]  # Remove leading 1
                    print(f"✅ USA/Canada detected: CC={found_cc}, Phone={found_phone}")
                
                # Check for other country codes
                if not found_cc:
                    for cc_length in range(4, 0, -1):
                        if len(digits) > cc_length:
                            possible_cc = digits[:cc_length]
                            possible_phone = digits[cc_length:]
                            
                            # SPECIAL: If cc is "1", convert to "11" for API
                            if possible_cc == '1':
                                found_cc = '11'
                                found_phone = possible_phone
                                break
                            # Check other country codes
                            elif possible_cc in ['7', '20', '27', '30', '31', '32', '33', '34', 
                                               '36', '39', '40', '41', '43', '44', '45', '46', 
                                               '47', '48', '49', '51', '52', '53', '54', '55', 
                                               '56', '57', '58', '60', '61', '62', '63', '64', 
                                               '65', '66', '81', '82', '84', '86', '90', '91', 
                                               '92', '93', '94', '95', '98', '212', '213', '216', 
                                               '218', '220', '221', '222', '223', '224', '225', 
                                               '226', '227', '228', '229', '230', '231', '232', 
                                               '233', '234', '235', '236', '237', '238', '239', 
                                               '240', '241', '242', '243', '244', '245', '246', 
                                               '247', '248', '249', '250', '251', '252', '253', 
                                               '254', '255', '256', '257', '258', '260', '261', 
                                               '262', '263', '264', '265', '266', '267', '268', 
                                               '269', '290', '291', '297', '298', '299', '350', 
                                               '351', '352', '353', '354', '355', '356', '357', 
                                               '358', '359', '370', '371', '372', '373', '374', 
                                               '375', '376', '377', '378', '379', '380', '381', 
                                               '382', '383', '385', '386', '387', '389', '420', 
                                               '421', '423', '500', '501', '502', '503', '504', 
                                               '505', '506', '507', '508', '509', '590', '591', 
                                               '592', '593', '594', '595', '596', '597', '598', 
                                               '599', '670', '672', '673', '674', '675', '676', 
                                               '677', '678', '679', '680', '681', '682', '683', 
                                               '685', '686', '687', '688', '689', '690', '691', 
                                               '692', '850', '852', '853', '855', '856', '880', 
                                               '886', '960', '961', '962', '963', '964', '965', 
                                               '966', '967', '968', '970', '971', '972', '973', 
                                               '974', '975', '976', '977', '992', '993', '994', 
                                               '995', '996', '998'] and 7 <= len(possible_phone) <= 15:
                                found_cc = possible_cc
                                found_phone = possible_phone
                                break
                
                # If no country code found, try default logic
                if not found_cc:
                    # Check if it starts with 1 (USA/Canada)
                    if digits.startswith('1'):
                        found_cc = '11'
                        found_phone = digits[1:] if len(digits) > 1 else digits
                    elif len(digits) == 10:
                        # Assume USA/Canada without country code
                        found_cc = '11'
                        found_phone = digits
                    elif len(digits) >= 7:
                        # Generic fallback
                        found_cc = '11'  # Default to USA/Canada
                        found_phone = digits
                
                if found_cc and found_phone:
                    all_numbers.append({
                        'cc': found_cc,
                        'phone': found_phone,
                        'source': 'digits_only'
                    })
                    print(f"✅ Extracted from digits: CC={found_cc}, Phone={found_phone}")
    
    # ৩. Remove duplicates based on phone number
    unique_numbers = []
    seen_phones = set()
    
    for num in all_numbers:
        phone = num['phone']
        # Also check for similar numbers (like 7869817 vs 47869817)
        if phone not in seen_phones:
            is_substring = False
            for seen_phone in seen_phones:
                if phone in seen_phone or seen_phone in phone:
                    is_substring = True
                    if len(phone) > len(seen_phone):
                        unique_numbers = [n for n in unique_numbers if n['phone'] != seen_phone]
                        seen_phones.remove(seen_phone)
                        unique_numbers.append(num)
                        seen_phones.add(phone)
                    break
            
            if not is_substring:
                unique_numbers.append(num)
                seen_phones.add(phone)
    
    print(f"🔍 Text: {text}")
    print(f"📱 Final extracted numbers: {unique_numbers}")
    
    return unique_numbers
    
async def add_number_async(session, token, cc, phone, retry_count=2):
    for attempt in range(retry_count):
        try:
            headers = {"Admin-Token": token}
            add_url = f"{BASE_URL}/z-number-base/addNum?cc={cc}&phoneNum={phone}&smsStatus=2"
            async with session.post(add_url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    print(f"✅ Number {phone} added successfully")
                    return True
                elif response.status == 401:
                    print(f"❌ Token expired during add for {phone}, attempt {attempt + 1}")
                    continue
                elif response.status in (400, 409):
                    print(f"❌ Number {phone} already exists or invalid, status {response.status}")
                    return False
                else:
                    print(f"❌ Add failed for {phone} with status {response.status}")
        except Exception as e:
            print(f"❌ Add number error for {phone} (attempt {attempt + 1}): {e}")
    return False

async def get_status_async(session, token, phone):
    try:
        headers = {"Admin-Token": token}
        status_url = f"{BASE_URL}/z-number-base/getAullNum?page=1&pageSize=15&phoneNum={phone}"
        
        async with session.get(status_url, headers=headers, timeout=10) as response:
            response_text = await response.text()
            
            if response.status == 401:
                print(f"❌ Token expired for {phone}")
                return -1, "❌ Token Expired", None
            
            try:
                res = await response.json(content_type=None)
            except Exception as json_error:
                print(f"❌ JSON parse attempt 1 failed for {phone}: {json_error}")
                try:
                    cleaned_text = response_text.strip()
                    if cleaned_text.startswith('\ufeff'):
                        cleaned_text = cleaned_text[1:]
                    res = json.loads(cleaned_text)
                except Exception as e2:
                    print(f"❌ Manual JSON parse also failed for {phone}: {e2}")
                    print(f"❌ Raw response: {response_text[:500]}")
                    return -2, "❌ API Error", None
            
            if res.get('code') == 28004:
                print(f"❌ Login required for {phone}")
                return -1, "❌ Token Expired", None
            
            if res.get('msg') and any(keyword in str(res.get('msg')).lower() for keyword in ["already exists", "cannot register", "number exists"]):
                print(f"❌ Number {phone} already exists or cannot register")
                return 16, "🚫 Already Exists", None
            
            if res.get('code') in (400, 409):
                print(f"❌ Number {phone} already exists, code {res.get('code')}")
                return 16, "🚫 Already Exists", None
            
            if (res and "data" in res and "records" in res["data"] and 
                res["data"]["records"] and len(res["data"]["records"]) > 0):
                record = res["data"]["records"][0]
                status_code = record.get("registrationStatus")
                record_id = record.get("id")
                status_name = status_map.get(status_code, f"🔸 Status {status_code}")
                return status_code, status_name, record_id
            
            if res and "data" in res and "records" in res["data"]:
                return None, "🚫 Already Registered...", None
            
            return None, "🚫 Already Registered...", None
            
    except Exception as e:
        print(f"❌ Status error for {phone}: {type(e).__name__}: {e}")
        return -2, "🔄 Refresh Server", None

async def delete_single_number_async(session, token, record_id, username):
    try:
        headers = {"Admin-Token": token}
        delete_url = f"{BASE_URL}/z-number-base/deleteNum/{record_id}"
        async with session.delete(delete_url, headers=headers, timeout=10) as response:
            if response.status == 200:
                return True
            else:
                print(f"❌ Delete failed for {record_id}: Status {response.status}")
                return False
    except Exception as e:
        print(f"❌ Delete error for {record_id}: {e}")
        return False

async def submit_otp_async(session, token, phone, code):
    try:
        headers = {"Admin-Token": token}
        otp_url = f"{BASE_URL}/z-number-base/allNum/uploadCode?phoneNum={phone}&code={code}"
        async with session.get(otp_url, headers=headers, timeout=10) as response:
            if response.status == 200:
                try:
                    result = await response.json(content_type=None)
                    if result.get('code') == 200:
                        print(f"✅ OTP submitted successfully for {phone}")
                        return True, "OTP verified successfully"
                    else:
                        print(f"❌ OTP submission failed for {phone}: {result.get('msg', 'Unknown error')}")
                        return False, result.get('msg', 'Unknown error')
                except:
                    text_result = await response.text()
                    if "success" in text_result.lower() or "200" in text_result:
                        print(f"✅ OTP submitted successfully for {phone} (text response)")
                        return True, "OTP verified successfully"
                    else:
                        print(f"❌ OTP submission failed for {phone}: {text_result}")
                        return False, text_result
            else:
                print(f"❌ OTP submission failed for {phone}: Status {response.status}")
                return False, f"HTTP Error: {response.status}"
    except Exception as e:
        print(f"❌ OTP submission error for {phone}: {e}")
        return False, str(e)

async def get_user_settlements(session, token, user_id, page=1, page_size=2):
    try:
        headers = {"Admin-Token": token}
        url = f"{BASE_URL}/m-settle-accounts/closingEntries?page={page}&pageSize={page_size}&userid={user_id}"
        
        print(f"🔍 Fetching settlements for user {user_id}")
        
        async with session.get(url, headers=headers, timeout=10) as response:
            response_text = await response.text()
            print(f"📥 Response status: {response.status}")
            
            if response.status == 200:
                try:
                    result = await response.json(content_type=None)
                    
                    if result.get('code') == 200:
                        data = result.get('data', {})
                        
                        if 'records' in data:
                            records = data.get('records', [])
                            total = data.get('total', len(records))
                            pages = data.get('pages', 1)
                            
                            return {
                                'records': records,
                                'total': total,
                                'pages': pages,
                                'page': page,
                                'size': page_size
                            }, None
                        else:
                            print(f"⚠️ No 'records' key in data: {data}")
                            return {
                                'records': [],
                                'total': 0,
                                'pages': 0,
                                'page': page,
                                'size': page_size
                            }, None
                    else:
                        error_msg = result.get('msg', 'Unknown error')
                        print(f"❌ API returned error: {error_msg}")
                        return None, f"API Error: {error_msg}"
                except Exception as e:
                    print(f"❌ JSON parse error in get_user_settlements: {e}")
                    return None, f"JSON parse error: {e}"
            else:
                print(f"❌ HTTP Error in get_user_settlements: {response.status}")
                return None, f"HTTP Error: {response.status}"
    except Exception as e:
        print(f"❌ Exception in get_user_settlements: {e}")
        return None, str(e)

class AccountManager:
    def __init__(self):
        print("🔄 Initializing Account Manager...")
        self.accounts = self._load_accounts_compatible()
        print(f"📊 Loaded accounts for {len(self.accounts)} users")
        
        self.user_tokens = {}
        self.token_owners = {}
        self.token_info = {}
        self.user_selected_accounts = {}
        self.user_accounts_data = {}  # Store user accounts data
        
    def _load_accounts_compatible(self):
        """Load accounts with backward compatibility"""
        try:
            accounts_data = load_accounts()
            
            # Check if old format (list) or new format (dict with accounts)
            converted_accounts = {}
            
            for user_id_str, user_data in accounts_data.items():
                if isinstance(user_data, list):
                    # Old format - convert to new format
                    accounts_list = user_data
                    converted_accounts[user_id_str] = {
                        "accounts": [],
                        "selected_account_id": 1,
                        "telegram_username": "",
                        "last_active": datetime.now().isoformat()
                    }
                    
                    for i, acc in enumerate(accounts_list, 1):
                        new_account = {
                            'id': i,
                            'custom_name': acc.get('custom_name', f"Account {i}"),
                            'username': acc.get('username', ''),
                            'password': acc.get('password', ''),
                            'token': acc.get('token'),
                            'api_user_id': acc.get('api_user_id'),
                            'nickname': acc.get('nickname', acc.get('username', '')),
                            'last_login': acc.get('last_login', datetime.now().isoformat()),
                            'active': acc.get('active', True),
                            'default': (i == 1),
                            'added_by': acc.get('added_by', 'unknown'),
                            'added_at': acc.get('added_at', datetime.now().isoformat()),
                            'telegram_username': acc.get('telegram_username', ''),
                            'friends': acc.get('friends', [])  # Add friends field
                        }
                        converted_accounts[user_id_str]["accounts"].append(new_account)
                    
                    print(f"✅ Converted old format for user {user_id_str}")
                elif isinstance(user_data, dict):
                    # Already in new format
                    converted_accounts[user_id_str] = user_data
                else:
                    print(f"❌ Invalid format for user {user_id_str}, resetting")
                    converted_accounts[user_id_str] = {
                        "accounts": [],
                        "selected_account_id": 1,
                        "telegram_username": "",
                        "last_active": datetime.now().isoformat()
                    }
            
            # Save converted format
            if converted_accounts != accounts_data:
                save_accounts(converted_accounts)
                print("✅ Accounts converted to new format")
            
            return converted_accounts
            
        except Exception as e:
            print(f"❌ Error loading accounts: {e}")
            return {}
    
    async def initialize_user(self, user_id):
        """Initialize accounts for a specific user"""
        user_id_str = str(user_id)
        
        # Load fresh accounts data
        self.accounts = self._load_accounts_compatible()
        
        user_data = self.accounts.get(user_id_str, {})
        if not user_data or not user_data.get("accounts"):
            print(f"ℹ️ No accounts found for user {user_id}")
            self.user_selected_accounts[user_id_str] = None
            return 0
            
        user_accounts = user_data["accounts"]
        selected_id = user_data.get("selected_account_id", 1)
        
        print(f"🔄 Initializing {len(user_accounts)} accounts for user {user_id}")
        print(f"📱 Selected account ID: {selected_id}")
        
        valid_tokens = []
        
        # Try to login to selected account
        selected_account = None
        for acc in user_accounts:
            if acc['id'] == selected_id:
                selected_account = acc
                break
        
        if not selected_account:
            # If selected account not found, use first account
            selected_account = user_accounts[0] if user_accounts else None
            selected_id = selected_account['id'] if selected_account else 1
        
        if selected_account and selected_account.get('active', True):
            username = selected_account['username']
            password = selected_account['password']
            custom_name = selected_account.get('custom_name', username)
            
            print(f"🔄 Logging into selected account: {custom_name}")
            
            # Check if we have valid token
            if selected_account.get('token') and selected_account.get('api_user_id'):
                print(f"🔍 Validating existing token for {username}")
                is_valid = await self.validate_token(selected_account['token'])
                if is_valid:
                    print(f"✅ Token valid for {username}")
                    valid_tokens.append((
                        username, 
                        selected_account['token'], 
                        selected_account['api_user_id'], 
                        custom_name,
                        selected_id
                    ))
                else:
                    print(f"🔄 Token invalid, re-logging in for {username}")
                    new_token, api_user_id, nickname = await login_api_async(username, password)
                    if new_token:
                        selected_account['token'] = new_token
                        selected_account['api_user_id'] = api_user_id
                        selected_account['nickname'] = nickname
                        selected_account['last_login'] = datetime.now().isoformat()
                        valid_tokens.append((
                            username, 
                            new_token, 
                            api_user_id, 
                            custom_name,
                            selected_id
                        ))
                        print(f"✅ Re-login successful for {username}")
                    else:
                        print(f"❌ Re-login failed for {username}")
                        selected_account['active'] = False
            else:
                print(f"🔄 First time login for {username}")
                new_token, api_user_id, nickname = await login_api_async(username, password)
                if new_token:
                    selected_account['token'] = new_token
                    selected_account['api_user_id'] = api_user_id
                    selected_account['nickname'] = nickname
                    selected_account['last_login'] = datetime.now().isoformat()
                    valid_tokens.append((
                        username, 
                        new_token, 
                        api_user_id, 
                        custom_name,
                        selected_id
                    ))
                    print(f"✅ First login successful for {username}")
                else:
                    print(f"❌ First login failed for {username}")
                    selected_account['active'] = False
        
        # Save updated accounts
        save_accounts(self.accounts)
        
        # Initialize token tracking
        self.user_tokens[user_id_str] = []
        self.user_selected_accounts[user_id_str] = selected_id
        
        for username, token, api_user_id, custom_name, account_id in valid_tokens:
            self.user_tokens[user_id_str].append(token)
            self.token_owners[token] = (user_id_str, username, custom_name, account_id)
            self.token_info[token] = {
                'username': username,
                'custom_name': custom_name,
                'api_user_id': api_user_id,
                'usage': 0,
                'account_id': account_id,
                'user_id': user_id_str
            }
        
        print(f"✅ Initialized {len(valid_tokens)} accounts for user {user_id}")
        return len(valid_tokens)
    
    async def validate_token(self, token):
        """Validate if token is still working"""
        try:
            async with aiohttp.ClientSession() as session:
                status_code, _, _ = await get_status_async(session, token, "0000000000")
                if status_code is not None and status_code != -1:
                    return True
            return False
        except Exception as e:
            print(f"❌ Token validation error: {e}")
            return False
    
    def get_user_accounts_count(self, user_id):
        """Get total number of accounts for user"""
        user_id_str = str(user_id)
        if user_id_str in self.accounts:
            user_data = self.accounts[user_id_str]
            if isinstance(user_data, dict):
                accounts = user_data.get("accounts", [])
            else:
                accounts = []
            active_accounts = [acc for acc in accounts if acc.get('active', True)]
            return len(active_accounts)
        return 0
    
    def get_user_active_accounts_count(self, user_id):
        """Get number of actively logged in accounts"""
        user_id_str = str(user_id)
        if user_id_str in self.user_tokens:
            return len(self.user_tokens[user_id_str])
        return 0
    
    def get_user_remaining_checks(self, user_id):
        """Calculate remaining checks for user - FIXED VERSION"""
        user_id_str = str(user_id)
        
        # Check if user has tokens
        if user_id_str not in self.user_tokens:
            return 0
        
        total_slots = 0
        used_slots = 0
        
        # Calculate total slots from all logged-in accounts
        for token in self.user_tokens[user_id_str]:
            if token in self.token_info:
                # Each account can handle MAX_PER_ACCOUNT checks
                total_slots += MAX_PER_ACCOUNT
                # Current usage of this token
                usage = self.token_info[token].get('usage', 0)
                used_slots += usage
        
        # Also check if user has accounts but not logged in
        if user_id_str in self.accounts:
            user_data = self.accounts[user_id_str]
            if isinstance(user_data, dict):
                accounts_list = user_data.get("accounts", [])
                active_accounts = [acc for acc in accounts_list if acc.get('active', True)]
                total_accounts = len(active_accounts)
                
                # Add potential slots for non-logged accounts
                logged_accounts = len(self.user_tokens[user_id_str])
                non_logged_accounts = total_accounts - logged_accounts
                total_slots += non_logged_accounts * MAX_PER_ACCOUNT
        
        remaining = max(0, total_slots - used_slots)
        
        # Debug info
        print(f"📊 Remaining check calculation for user {user_id}:")
        print(f"  Total slots: {total_slots}")
        print(f"  Used slots: {used_slots}")
        print(f"  Remaining: {remaining}")
        
        return remaining
    
    def get_selected_account_name(self, user_id):
        """Get custom name of selected account"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.accounts:
            return "Unknown"
        
        user_data = self.accounts[user_id_str]
        if not isinstance(user_data, dict):
            return "Unknown"
            
        selected_id = user_data.get("selected_account_id", 1)
        
        for acc in user_data.get("accounts", []):
            if acc['id'] == selected_id:
                return acc.get('custom_name', acc.get('username', 'Unknown'))
        
        return "Unknown"
    
    def get_selected_account_id(self, user_id):
        """Get selected account ID"""
        user_id_str = str(user_id)
        return self.user_selected_accounts.get(user_id_str, 1)
    
    def get_user_accounts_info(self, user_id):
        """Get detailed accounts info for user"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.accounts:
            return []
        
        accounts_info = []
        user_data = self.accounts[user_id_str]
        if not isinstance(user_data, dict):
            return []
            
        selected_id = user_data.get("selected_account_id", 1)
        
        for acc in user_data.get("accounts", []):
            account_info = {
                'id': acc['id'],
                'custom_name': acc.get('custom_name', f"Account {acc['id']}"),
                'username': acc['username'],
                'api_user_id': acc.get('api_user_id'),
                'active': acc.get('active', True),
                'logged_in': bool(acc.get('token')),
                'selected': (acc['id'] == selected_id),
                'last_login': acc.get('last_login'),
                'default': acc.get('default', False)
            }
            accounts_info.append(account_info)
        
        return accounts_info
    
    def get_next_available_token(self, user_id):
        """Get next available token for processing - FIXED VERSION"""
        user_id_str = str(user_id)
        if user_id_str not in self.user_tokens or not self.user_tokens[user_id_str]:
            print(f"❌ No valid tokens available for user {user_id}")
            return None
        
        available_tokens = []
        for token in self.user_tokens[user_id_str]:
            info = self.token_info.get(token, {})
            usage = info.get('usage', 0)
            if usage < MAX_PER_ACCOUNT:
                custom_name = info.get('custom_name', 'Unknown')
                account_id = info.get('account_id', 0)
                available_tokens.append((token, usage, custom_name, account_id))
        
        if not available_tokens:
            print(f"❌ All accounts are at maximum usage for user {user_id}")
            return None
        
        # Get token with lowest usage
        best_token, best_usage, custom_name, account_id = min(available_tokens, key=lambda x: x[1])
        
        # Check if we can use this token
        if best_usage >= MAX_PER_ACCOUNT:
            print(f"❌ Token {custom_name} already at max usage {best_usage}/{MAX_PER_ACCOUNT}")
            return None
        
        # Increment usage
        self.token_info[best_token]['usage'] += 1
        
        current_usage = self.token_info[best_token]['usage']
        print(f"✅ Using token from {custom_name} (ID: {account_id}), usage: {current_usage}/{MAX_PER_ACCOUNT}")
        
        return best_token, custom_name
    
    def release_token(self, token):
        """Release token after processing - FIXED VERSION"""
        if token in self.token_info:
            current_usage = self.token_info[token]['usage']
            
            # Only decrement if usage is greater than 0
            if current_usage > 0:
                self.token_info[token]['usage'] = current_usage - 1
                
                custom_name = self.token_info[token].get('custom_name', 'Unknown')
                new_usage = self.token_info[token]['usage']
                print(f"✅ Released token from {custom_name}, usage: {new_usage}/{MAX_PER_ACCOUNT}")
            else:
                print(f"⚠️ Token {token} already at 0 usage, nothing to release")
    
    def get_api_user_id_for_token(self, token):
        """Get API user ID for a token"""
        info = self.token_info.get(token, {})
        return info.get('api_user_id')
    
    def get_account_info_for_token(self, token):
        """Get account info for a token"""
        if token in self.token_info:
            return self.token_info[token].copy()
        return {}
    
    def switch_user_account(self, user_id, account_id):
        """Switch user's selected account"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.accounts:
            return False
        
        user_data = self.accounts[user_id_str]
        if not isinstance(user_data, dict):
            return False
        
        # Check if account exists
        account_exists = False
        for acc in user_data.get("accounts", []):
            if acc['id'] == account_id:
                account_exists = True
                break
        
        if not account_exists:
            return False
        
        # Update selected account
        self.accounts[user_id_str]["selected_account_id"] = account_id
        self.accounts[user_id_str]["last_active"] = datetime.now().isoformat()
        self.user_selected_accounts[user_id_str] = account_id
        
        # Save changes
        save_accounts(self.accounts)
        
        print(f"✅ User {user_id} switched to account ID: {account_id}")
        return True
    
    async def refresh_user_account(self, user_id, account_id=None):
        """Refresh specific account or all accounts for user"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.accounts:
            return False
        
        user_data = self.accounts[user_id_str]
        if not isinstance(user_data, dict):
            return False
        
        updated_count = 0
        user_accounts = user_data.get("accounts", [])
        
        if account_id:
            # Refresh specific account
            for acc in user_accounts:
                if acc['id'] == account_id and acc.get('active', True):
                    token, api_user_id, nickname = await login_api_async(
                        acc['username'], 
                        acc['password']
                    )
                    if token:
                        acc['token'] = token
                        acc['api_user_id'] = api_user_id
                        acc['nickname'] = nickname
                        acc['last_login'] = datetime.now().isoformat()
                        updated_count += 1
                        print(f"✅ Refreshed account: {acc.get('custom_name', acc['username'])}")
                    break
        else:
            # Refresh all accounts
            for acc in user_accounts:
                if acc.get('active', True):
                    token, api_user_id, nickname = await login_api_async(
                        acc['username'], 
                        acc['password']
                    )
                    if token:
                        acc['token'] = token
                        acc['api_user_id'] = api_user_id
                        acc['nickname'] = nickname
                        acc['last_login'] = datetime.now().isoformat()
                        updated_count += 1
        
        self.accounts[user_id_str]["last_active"] = datetime.now().isoformat()
        save_accounts(self.accounts)
        
        # Re-initialize user
        await self.initialize_user(user_id)
        
        print(f"✅ Refreshed {updated_count} accounts for user {user_id}")
        return updated_count
    
    def get_all_users_accounts(self):
        """Get all users accounts for admin view"""
        all_users = {}
        
        for user_id_str, user_data in self.accounts.items():
            if user_id_str == str(ADMIN_ID):
                continue
            
            if not isinstance(user_data, dict):
                continue
                
            if user_data and "accounts" in user_data:
                user_info = {
                    'user_id': user_id_str,
                    'telegram_username': user_data.get('telegram_username', ''),
                    'last_active': user_data.get('last_active', ''),
                    'selected_account_id': user_data.get('selected_account_id', 1),
                    'accounts': []
                }
                
                for acc in user_data.get("accounts", []):
                    account_info = {
                        'id': acc['id'],
                        'custom_name': acc.get('custom_name', f"Account {acc['id']}"),
                        'username': acc['username'],
                        'api_user_id': acc.get('api_user_id'),
                        'active': acc.get('active', True),
                        'logged_in': bool(acc.get('token')),
                        'last_login': acc.get('last_login'),
                        'added_by': acc.get('added_by', 'unknown'),
                        'added_at': acc.get('added_at', '')
                    }
                    user_info['accounts'].append(account_info)
                
                all_users[user_id_str] = user_info
        
        return all_users

# Initialize AccountManager
account_manager = AccountManager()

active_numbers = {}

number_status_history = {}

async def handle_otp_submission(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if update.message.reply_to_message:
        replied_message = update.message.reply_to_message.text
        print(f"🔍 Checking OTP submission - User: {user_id}, Text: {text}")
        print(f"📩 Replied message: {replied_message}")
        
        # নম্বর এক্সট্র্যাক্ট করা
        phone_match = re.search(r'(\d{10})', replied_message)
        if phone_match:
            phone = phone_match.group(1)
            print(f"📱 Found phone in reply: {phone}")
            
            # ডিবাগ: active_numbers কি আছে?
            print(f"📊 Active numbers in memory: {len(active_numbers)}")
            if active_numbers:
                for num, data in list(active_numbers.items())[:5]:  # প্রথম ৫টি দেখাবে
                    print(f"  - {num}: user_id={data.get('user_id')}, username={data.get('username')}")
            
            if phone in active_numbers:
                otp_data = active_numbers[phone]
                token = otp_data['token']
                username = otp_data['username']
                message_id = otp_data['message_id']
                data_user_id = otp_data['user_id']
                
                print(f"✅ Phone {phone} found in active_numbers")
                print(f"   Token exists: {bool(token)}")
                print(f"   Message ID: {message_id}")
                print(f"   Data User ID: {data_user_id}")
                print(f"   Current User ID: {user_id}")
                
                # চেক করুন ইউজার সঠিক কিনা
                if data_user_id == user_id:
                    if re.match(r'^\d{4,6}$', text):
                        processing_msg = await update.message.reply_text(f"🔄 Submitting OTP for {phone}...")
                        
                        async with aiohttp.ClientSession() as session:
                            success, message = await submit_otp_async(session, token, phone, text)
                        
                        if success:
                            await processing_msg.delete()
                            
                            # OTP সাবমিট সফল হলে status চেক করুন
                            async with aiohttp.ClientSession() as session:
                                status_code, status_name, record_id = await get_status_async(session, token, phone)
                            
                            try:
                                await context.bot.edit_message_text(
                                    chat_id=update.effective_chat.id,
                                    message_id=message_id,
                                    text=f"{phone} {status_name}"
                                )
                                
                                # OTP stats update
                                if status_code == 1:
                                    otp_stats = load_otp_stats()
                                    user_id_str = str(user_id)
                                    
                                    if user_id_str not in otp_stats["user_stats"]:
                                        otp_stats["user_stats"][user_id_str] = {
                                            "total_success": 0,
                                            "today_success": 0,
                                            "yesterday_success": 0,
                                            "username": username,
                                            "full_name": ""
                                        }
                                    
                                    otp_stats["user_stats"][user_id_str]["total_success"] += 1
                                    otp_stats["user_stats"][user_id_str]["today_success"] += 1
                                    otp_stats["today_success"] += 1
                                    otp_stats["total_success"] += 1
                                    
                                    save_otp_stats(otp_stats)
                                    print(f"✅ OTP success stats updated for user {user_id_str}")
                                
                            except BadRequest as e:
                                print(f"⚠️ Could not update message after OTP: {e}")
                                await update.message.reply_text(f"✅ OTP submitted successfully for {phone}")
                        else:
                            await processing_msg.edit_text(f"❌ OTP submission failed for {phone}: {message}")
                    else:
                        await update.message.reply_text("❌ Invalid OTP format. Please send 4-6 digit OTP code.")
                else:
                    print(f"❌ User mismatch: data_user_id={data_user_id}, user_id={user_id}")
                    await update.message.reply_text("❌ This number is not active or doesn't belong to you.")
            else:
                print(f"❌ Phone {phone} not found in active_numbers")
                await update.message.reply_text("❌ This number is not active or doesn't belong to you.")
        else:
            await update.message.reply_text("❌ Please reply to a number message with OTP code.")
    else:
        await update.message.reply_text("❌ Please reply to a number message with OTP code.")

async def track_status_optimized(context: CallbackContext):
    data = context.job.data
    phone = data['phone']
    token = data['token']
    username = data['username']
    user_id = data['user_id']
    checks = data['checks']
    last_status = data.get('last_status', '🔵 Processing...')
    serial_number = data.get('serial_number')
    last_status_code = data.get('last_status_code')
    cc = data.get('cc', '1')
    
    try:
        async with aiohttp.ClientSession() as session:
            status_code, status_name, record_id, actual_phone = await get_status_with_actual_phone(session, token, phone)
        
        prefix = f"{serial_number}. " if serial_number else ""
        display_phone = actual_phone if actual_phone and actual_phone != phone else phone
        
        # ============ DEBUG INFO ============
        print(f"🔍 Checking {phone}: Status={status_code}, Record_ID={record_id}")
        # ====================================
        
        # ============ IMPORTANT FIX ============
        # সব স্ট্যাটাসের জন্য ইউনিফাইড লজিক
        if status_code is not None and status_code not in [1, 2]:
            # স্ট্যাটাস ১ (সাকসেস) এবং ২ (ইন প্রোগ্রেস) ছাড়া বাকি সব ডিলিট হবে
            print(f"🛑 FINAL STATE for {phone}: Status {status_code} - DELETING...")
            
            # টোকেন রিলিজ (কিন্তু শুধুমাত্র সাকসেস না হলে)
            account_manager.release_token(token)
            
            # active_numbers থেকে রিমুভ
            if phone in active_numbers:
                del active_numbers[phone]
                print(f"🗑️ Removed from active_numbers")
            
            # ডিলিট প্রসেস শুরু
            print(f"🔴 Starting deletion process...")
            
            # ১. API থেকে রেকর্ড আইডি দিয়ে ডিলিট
            if record_id:
                print(f"📝 Deleting from API with record_id: {record_id}")
                async with aiohttp.ClientSession() as session:
                    api_deleted = await delete_single_number_async(session, token, record_id, username)
                    if api_deleted:
                        print(f"✅ API deletion successful")
                    else:
                        print(f"❌ API deletion failed, trying alternative")
            
            # ২. ইউজারের সব অ্যাকাউন্ট থেকে ডিলিট
            print(f"🔄 Deleting from all user accounts")
            deleted_count = await delete_number_from_all_accounts_optimized(phone, user_id)
            print(f"✅ Deleted from {deleted_count} user accounts")
            
            # ফাইনাল মেসেজ
            final_text = f"{prefix}+{cc} {display_phone} {status_name}"
            if actual_phone and actual_phone != phone:
                final_text += f""
            
            try:
                await context.bot.edit_message_text(
                    chat_id=data['chat_id'], 
                    message_id=data['message_id'],
                    text=final_text
                )
                print(f"📨 Message updated successfully")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    print(f"⚠️ Message update error: {e}")
            
            return  # 🛑 ট্র্যাকিং বন্ধ
        
        # ============ সাকসেস হ্যান্ডলিং ============
        if status_code == 1 and last_status_code != 1:
            print(f"🎉 SUCCESS for {phone}")
            
            # টোকেন রিলিজ কিন্তু কাউন্ট রাখা
            account_manager.release_token(token)
            
            # active_numbers থেকে রিমুভ
            if phone in active_numbers:
                del active_numbers[phone]
                print(f"🗑️ Removed from active_numbers (SUCCESS)")
            
            # স্ট্যাটিস্টিক্স আপডেট
            tracking = load_tracking()
            user_id_str = str(user_id)
            
            if phone not in tracking.get("today_success", {}):
                otp_stats = load_otp_stats()
                otp_stats["total_success"] = otp_stats.get("total_success", 0) + 1
                otp_stats["today_success"] = otp_stats.get("today_success", 0) + 1
                
                if user_id_str not in otp_stats["user_stats"]:
                    otp_stats["user_stats"][user_id_str] = {
                        "total_success": 0,
                        "today_success": 0,
                        "yesterday_success": 0,
                        "username": username,
                        "full_name": ""
                    }
                otp_stats["user_stats"][user_id_str]["total_success"] += 1
                otp_stats["user_stats"][user_id_str]["today_success"] += 1
                
                tracking["today_success"][phone] = user_id_str
                
                if "today_success_counts" not in tracking:
                    tracking["today_success_counts"] = {}
                
                if user_id_str not in tracking["today_success_counts"]:
                    tracking["today_success_counts"][user_id_str] = 0
                tracking["today_success_counts"][user_id_str] += 1
                
                save_otp_stats(otp_stats)
                save_tracking(tracking)
                print(f"✅ Success stats updated")
            
            # সাকসেস মেসেজ
            final_text = f"{prefix}+{cc} {display_phone} {status_name}"
            try:
                await context.bot.edit_message_text(
                    chat_id=data['chat_id'], 
                    message_id=data['message_id'],
                    text=final_text
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    print(f"⚠️ Success message update error: {e}")
            
            return  # 🛑 ট্র্যাকিং বন্ধ
        
        # ============ ইন প্রোগ্রেস হ্যান্ডলিং ============
        if status_code == 2:
            if phone not in active_numbers:
                active_numbers[phone] = {
                    'token': token,
                    'username': username,
                    'message_id': data['message_id'],
                    'user_id': user_id,
                    'chat_id': data['chat_id']
                }
                print(f"✅ Added to active_numbers for OTP")
        
        # ============ স্ট্যাটাস আপডেট ============
        if status_name != last_status:
            new_text = f"{prefix}+{cc} {display_phone} {status_name}"
            if actual_phone and actual_phone != phone:
                new_text += f""
            
            try:
                await context.bot.edit_message_text(
                    chat_id=data['chat_id'], 
                    message_id=data['message_id'],
                    text=new_text
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    print(f"⚠️ Status update error: {e}")
        
        # ============ টাইমআউট চেক ============
        if checks >= 100:
            print(f"⏰ TIMEOUT for {phone} after {checks} checks")
            account_manager.release_token(token)
            
            if phone in active_numbers:
                del active_numbers[phone]
                print(f"🗑️ Removed from active_numbers (timeout)")
            
            # টাইমআউট হলে ডিলিট করুন
            if status_code not in [1, 2]:
                print(f"🔴 Timeout - deleting {phone}")
                if record_id:
                    async with aiohttp.ClientSession() as session:
                        await delete_single_number_async(session, token, record_id, username)
                await delete_number_from_all_accounts_optimized(phone, user_id)
            
            timeout_text = f"{prefix}+{cc} {display_phone} 🟡 Try Later"
            if actual_phone and actual_phone != phone:
                timeout_text += f""
            
            try:
                await context.bot.edit_message_text(
                    chat_id=data['chat_id'], 
                    message_id=data['message_id'],
                    text=timeout_text
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    print(f"❌ Timeout message update error: {e}")
            
            return
        
        # ============ পরবর্তী চেক শিডিউল ============
        if context.job_queue:
            context.job_queue.run_once(
                track_status_optimized, 
                2,
                data={
                    **data, 
                    'checks': checks + 1, 
                    'last_status': status_name,
                    'last_status_code': status_code,
                    'cc': cc
                }
            )
        else:
            print("❌ JobQueue unavailable")
            
    except Exception as e:
        print(f"❌ Tracking error for {phone}: {e}")
        account_manager.release_token(token)

async def delete_number_from_all_accounts_optimized(phone, user_id):
    """ডিলিট নাম্বার ইউজারের সব অ্যাকাউন্ট থেকে"""
    accounts = load_accounts()
    user_id_str = str(user_id)
    deleted_count = 0
    
    user_data = accounts.get(user_id_str, {})
    if not isinstance(user_data, dict):
        return 0
    
    # ইউজারের সব অ্যাকাউন্ট থেকে ডিলিট করার টাস্ক তৈরি করুন
    async with aiohttp.ClientSession() as session:
        tasks = []
        
        # ইউজারের প্রতিটি অ্যাকাউন্টের জন্য
        for account in user_data.get("accounts", []):
            if account.get("token"):
                # চেক করুন নাম্বারটি এই অ্যাকাউন্টে আছে কিনা
                task = asyncio.create_task(
                    check_and_delete_number(session, account["token"], phone, account['username'])
                )
                tasks.append(task)
        
        if tasks:
            # সব টাস্ক একসাথে রান করুন
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, bool) and result:
                    deleted_count += 1
        
        # স্ট্যাটিস্টিক্স আপডেট
        stats = load_stats()
        stats["total_deleted"] = stats.get("total_deleted", 0) + deleted_count
        stats["today_deleted"] = stats.get("today_deleted", 0) + deleted_count
        save_stats(stats)
        
        print(f"✅ Deleted {phone} from {deleted_count} accounts of user {user_id}")
        return deleted_count

async def check_and_delete_number(session, token, phone, username):
    """চেক করে নাম্বার ডিলিট করুন"""
    try:
        # প্রথমে স্ট্যাটাস চেক করুন
        status_code, status_name, record_id, _ = await get_status_with_actual_phone(session, token, phone)
        
        if record_id:
            # রেকর্ড আইডি থাকলে ডিলিট করুন
            deleted = await delete_single_number_async(session, token, record_id, username)
            if deleted:
                print(f"✅ Deleted {phone} from {username}'s account")
                return True
        else:
            # রেকর্ড না থাকলে শুধু ট্রু রিটার্ন করুন
            print(f"ℹ️ No record found for {phone} in {username}'s account")
            return True
            
    except Exception as e:
        print(f"❌ Error deleting {phone} from {username}: {e}")
    
    return False

async def delete_if_exists(session, token, phone, username):
    try:
        status_code, _, record_id = await get_status_async(session, token, phone)
        if record_id:
            return await delete_single_number_async(session, token, record_id, username)
        return True
    except Exception as e:
        print(f"❌ Delete check error for {phone} in {username}: {e}")
        return False

async def show_user_settlements(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    
    if user_id_str not in account_manager.user_tokens or not account_manager.user_tokens[user_id_str]:
        await update.message.reply_text("❌ No active accounts found!")
        return
    
    token = account_manager.user_tokens[user_id_str][0]
    
    api_user_id = account_manager.get_api_user_id_for_token(token)
    
    if not api_user_id:
        await update.message.reply_text(
            "❌ Could not find your API user ID.\n\n"
            "Please refresh your accounts by clicking '🚀 Refresh Server' button first."
        )
        return
    
    page = 1
    if context.args:
        try:
            page = int(context.args[0])
            if page < 1:
                page = 1
        except:
            pass
    
    processing_msg = await update.message.reply_text("🔄 Loading your settlement records...")
    
    async with aiohttp.ClientSession() as session:
        data, error = await get_user_settlements(session, token, str(api_user_id), page=page, page_size=5)
    
    if error:
        await processing_msg.edit_text(f"❌ Error loading settlements: {error}")
        return
    
    if not data or not data.get('records'):
        await processing_msg.edit_text("❌ No settlement records found for your account!")
        return
    
    records = data.get('records', [])
    total_records = data.get('total', 0)
    total_pages = data.get('pages', 1)
    
    total_count = 0
    total_amount = 0
    for record in records:
        count = record.get('count', 0)
        record_rate = record.get('receiptPrice', 0.10)
        total_count += count
        total_amount += count * record_rate
    
    message = f"📦 Your Settlement Records\n\n"
    message += f"📊 Total Records: {total_records}\n"
    message += f"🔢 Total Count: {total_count}\n"
    message += f"📄 Page: {page}/{total_pages}\n\n"
    
    for i, record in enumerate(records, 1):
        record_id = record.get('id', 'N/A')
        if record_id != 'N/A' and len(str(record_id)) > 8:
            record_id = str(record_id)[:8] + '...'
        
        count = record.get('count', 0)
        record_rate = record.get('receiptPrice', 0.10)
        amount = count * record_rate
        gmt_create = record.get('gmtCreate', 'N/A')
        country = record.get('countryName', 'N/A') or record.get('country', 'N/A')
        
        try:
            if gmt_create != 'N/A':
                if 'T' in gmt_create:
                    date_obj = datetime.fromisoformat(gmt_create.replace('Z', '+00:00'))
                else:
                    date_obj = datetime.strptime(gmt_create, '%Y-%m-%d %H:%M:%S')
                formatted_date = date_obj.strftime('%d %B %Y, %H:%M')
            else:
                formatted_date = 'N/A'
        except:
            formatted_date = gmt_create
        
        message += f"{i}. Settlement #{record_id}\n"
        message += f"📅 Date: {formatted_date}\n"
        message += f"🌍 Country: {country}\n"
        message += f"🔢 Count: {count}\n\n"
        
    
    keyboard = []
    row = []
    
    if page > 1:
        row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"settlement_{page-1}"))
    
    if page < total_pages:
        if not row:
            row = []
        row.append(InlineKeyboardButton("Next ➡️", callback_data=f"settlement_{page+1}"))
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data=f"settlement_refresh_{page}")])
    
    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)
        await processing_msg.edit_text(message, reply_markup=reply_markup, parse_mode='none')
    else:
        await processing_msg.edit_text(message, parse_mode='none')

async def set_settlement_rate(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
        
    if not context.args:
        await update.message.reply_text(
            "✨ Set Settlement Rate ✨\n\n"
            "📝 Usage: `/setrate [country_rate_pairs] [date]`\n"
            "📢 Notice: `/setrate notice Your message here`\n\n"
            "📌 Examples:\n"
            "• `/setrate 0.08` (Today, all countries)\n"
            "• `/setrate 0.07 canada 0.04 benin 0.09 nigeria` (Different rates per country)\n"
            "• `/setrate 0.07 canada 0.04 benin 2/12` (2nd Dec, different rates)\n"
            "• `/setrate notice Payment will be sent tomorrow` (Send notice)\n\n"
            "💡 Note: Date format: DD/MM or YYYY-MM-DD"
        )
        return
        
    try:
        if context.args[0].lower() == 'notice':
            notice_message = ' '.join(context.args[1:])
            if not notice_message:
                await update.message.reply_text("❌ Please provide a notice message!")
                return
            
            accounts = load_accounts()
            sent_count = 0
            
            processing_msg = await update.message.reply_text(f"📢 Sending notice to all users...")
            
            for user_id_str, user_data in accounts.items():
                if user_id_str == str(ADMIN_ID):
                    continue
                
                try:
                    await context.bot.send_message(
                        int(user_id_str),
                        f"📢 Admin Notice 📢\n\n"
                        f"{notice_message}\n\n"
                        f"📅 Date: {datetime.now().strftime('%d %B %Y')}"
                    )
                    sent_count += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"❌ Could not send notice to user {user_id_str}: {e}")
            
            await processing_msg.edit_text(
                f"✅ Notice Sent Successfully!\n\n"
                f"📢 Message: {notice_message}\n"
                f"👥 Sent to: {sent_count} users\n"
                f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
            )
            return
        
        # Parse country-specific rates
        country_rates = {}
        target_date = datetime.now().date()
        date_provided = False
        
        args = context.args.copy()
        
        # Check if last argument is a date
        if len(args) >= 2 and ('/' in args[-1] or '-' in args[-1]):
            date_str = args[-1]
            args = args[:-1]  # Remove date from args
            
            try:
                if '/' in date_str:
                    parts = date_str.split('/')
                    if len(parts) == 2:
                        day, month = parts
                        if len(day) == 1:
                            day = '0' + day
                        if len(month) == 1:
                            month = '0' + month
                        current_year = datetime.now().year
                        target_date = datetime.strptime(f"{day}/{month}/{current_year}", "%d/%m/%Y").date()
                elif '-' in date_str:
                    if len(date_str) == 5:
                        month, day = date_str.split('-')
                        current_year = datetime.now().year
                        target_date = datetime.strptime(f"{current_year}-{month}-{day}", "%Y-%m-%d").date()
                    else:
                        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                date_provided = True
                print(f"📅 Date parsed: {target_date}")
            except Exception as e:
                print(f"⚠️ Date parsing error: {e}")
                # If date parsing fails, treat it as part of country rates
                args.append(date_str)
        
        # Parse country rates
        i = 0
        default_rate = None
        
        while i < len(args):
            try:
                rate = float(args[i])
                
                # Check if next token is a country name
                if i + 1 < len(args) and not args[i+1].replace('.', '', 1).isdigit():
                    country_name = args[i+1].title()
                    country_rates[country_name] = rate
                    print(f"✅ Country rate: {country_name} = ${rate}")
                    i += 2
                else:
                    # Default rate for all countries
                    default_rate = rate
                    print(f"✅ Default rate: ${rate}")
                    i += 1
            except ValueError:
                # If not a number, might be a country name without rate
                print(f"⚠️ Skipping invalid rate: {args[i]}")
                i += 1
        
        if not default_rate and not country_rates:
            await update.message.reply_text("❌ Please provide at least one rate!")
            return
        
        # If no country rates specified, use default for all
        if not country_rates and default_rate:
            print(f"ℹ️ Using default rate for all countries: ${default_rate}")
        
        settings = load_settings()
        old_rate = settings.get('settlement_rate', 0.10)
        
        target_date_str = target_date.strftime('%Y-%m-%d')
        target_date_display = target_date.strftime('%d %B %Y')
        
        # Create filter message
        filter_message = ""
        if country_rates:
            if len(country_rates) == 1:
                country = list(country_rates.keys())[0]
                rate = country_rates[country]
                filter_message = f"🌍 Country: {country} only (${rate:.3f}/count)"
            else:
                filter_message = "🌍 Countries & Rates:\n"
                for country, rate in country_rates.items():
                    filter_message += f"• {country}: ${rate:.3f}/count\n"
        else:
            filter_message = f"🌍 All Countries (${default_rate:.3f}/count)"
        
        processing_msg = await update.message.reply_text(
            f"🔄 Processing Settlement Rate Update\n\n"
            f"📅 Date: {target_date_display}\n"
            f"{filter_message}\n"
            f"⏳ Status: Initializing users..."
        )
        
        accounts = load_accounts()
        all_users_summary = []
        total_users = 0
        total_usd = 0
        total_bdt = 0
        USD_TO_BDT = 124
        
        users_processed = 0
        users_token_refreshed = 0
        users_with_settlements = 0
        users_with_only_commission = 0
        users_failed = 0
        
        # Track users with earnings
        users_with_earnings = 0
        users_without_earnings = 0
        
        # টোটাল স্ট্যাটিসটিক্স
        total_friends_count = 0
        total_eligible_friends = 0
        total_personal_count = 0
        total_friend_counts = 0
        
        # প্রতিটি ইউজারের জন্য কে কার অধীনে কাজ করছে তা ট্র্যাক করা
        user_under_supervisors = {}
        
        print(f"🔍 Total users in accounts: {len(accounts)}")
        
        for user_id_str, user_data in accounts.items():
            if user_id_str == str(ADMIN_ID):
                continue
            
            if not isinstance(user_data, dict):
                continue
                
            user_accounts = user_data.get("accounts", [])
            if not user_accounts:
                continue
            
            users_processed += 1
            username = user_accounts[0].get('username', 'Unknown') if user_accounts else 'Unknown'
            telegram_username = user_accounts[0].get('telegram_username', '') if user_accounts else ''
            
            if users_processed % 5 == 0:
                try:
                    await processing_msg.edit_text(
                        f"🔄 Processing Settlement Rate Update\n\n"
                        f"📅 Date: {target_date_display}\n"
                        f"{filter_message}\n"
                        f"⏳ Status: Processing {users_processed} users...\n"
                        f"✅ With Earnings: {users_with_earnings}\n"
                        f"👥 Without Earnings: {users_without_earnings}"
                    )
                except:
                    pass
            
            user_token = None
            token_refreshed = False
            
            if user_id_str in account_manager.user_tokens and account_manager.user_tokens[user_id_str]:
                user_token = account_manager.user_tokens[user_id_str][0]
                
                async with aiohttp.ClientSession() as session:
                    status_code, _, _ = await get_status_async(session, user_token, "0000000000")
                
                if status_code == -1:
                    user_token = None
            
            if not user_token:
                for acc in user_accounts:
                    if not acc.get('active', True):
                        continue
                    
                    token, api_user_id, nickname = await login_api_async(acc['username'], acc['password'])
                    if token:
                        acc['token'] = token
                        acc['api_user_id'] = api_user_id
                        acc['nickname'] = nickname
                        acc['last_login'] = datetime.now().isoformat()
                        
                        user_token = token
                        token_refreshed = True
                        users_token_refreshed += 1
                        break
            
            if not user_token:
                users_failed += 1
                continue
            
            save_accounts(accounts)
            
            api_user_id = None
            for acc in user_accounts:
                if acc.get('token') == user_token:
                    api_user_id = acc.get('api_user_id')
                    break
            
            if not api_user_id:
                users_failed += 1
                continue
            
            try:
                print(f"\n📊 Processing user: {username} (ID: {user_id_str})")
                
                # ১. প্রথমে ইউজারের নিজের settlement চেক করা
                user_filtered_settlements = []
                country_totals = {}
                total_count = 0
                total_usd_user = 0
                
                async with aiohttp.ClientSession() as session:
                    settlement_data, error = await get_user_settlements(session, user_token, str(api_user_id), page=1, page_size=100)
                
                if not error and settlement_data and settlement_data.get('records'):
                    for record in settlement_data.get('records', []):
                        gmt_create = record.get('gmtCreate')
                        if not gmt_create:
                            continue
                        
                        try:
                            if 'T' in gmt_create:
                                record_date = datetime.fromisoformat(gmt_create.replace('Z', '+00:00')).date()
                            else:
                                record_date = datetime.strptime(gmt_create, '%Y-%m-%d %H:%M:%S').date()
                            
                            if record_date != target_date:
                                continue
                            
                            country = record.get('countryName') or record.get('country') or 'Unknown'
                            
                            # Check if this country is included in our rates
                            if country_rates:
                                country_matched = False
                                matched_country = None
                                
                                for target_country in country_rates.keys():
                                    if target_country.lower() in country.lower() or country.lower() in target_country.lower():
                                        country_matched = True
                                        matched_country = target_country
                                        break
                                
                                if not country_matched:
                                    continue
                            # If no country rates specified, use default rate
                            elif not default_rate:
                                continue
                            
                            user_filtered_settlements.append({
                                'record': record,
                                'date': record_date,
                                'country': country,
                                'count': record.get('count', 0)
                            })
                            
                        except Exception as e:
                            continue
                
                if user_filtered_settlements:
                    users_with_settlements += 1
                    
                    for item in user_filtered_settlements:
                        country = item['country']
                        if country not in country_totals:
                            country_totals[country] = 0
                        country_totals[country] += item['count']
                    
                    total_count = sum(country_totals.values())
                    
                    # Calculate earnings based on country rates
                    for country, count in country_totals.items():
                        if country_rates:
                            # Find matching country rate
                            rate = default_rate
                            for target_country, target_rate in country_rates.items():
                                if target_country.lower() in country.lower() or country.lower() in target_country.lower():
                                    rate = target_rate
                                    break
                        else:
                            rate = default_rate
                        
                        total_usd_user += count * rate
                    
                    total_personal_count += total_count
                    print(f"✅ User has settlements: {total_count} counts = ${total_usd_user:.2f}")
                else:
                    print(f"⚠️ User {username} has no settlements on {target_date}")
                
                # ২. ফ্রেন্ডদের কমিশন যোগ করা
                commission_rate = 0.002
                total_commission = 0
                friends_details = []
                
                # ফ্রেন্ড ডেটা চেক করা
                friends_list = []
                for acc in user_accounts:
                    if isinstance(acc, dict) and 'friends' in acc and isinstance(acc['friends'], list):
                        friends_list = acc['friends']
                        print(f"👥 Found {len(friends_list)} friends for {username}")
                        break
                
                total_friends_count += len(friends_list)
                
                # প্রতিটি ফ্রেন্ডের জন্য কমিশন ক্যালকুলেশন
                for friend_data in friends_list:
                    friend_user_id = None
                    
                    if isinstance(friend_data, dict) and 'user_id' in friend_data:
                        friend_user_id = str(friend_data['user_id'])
                    elif isinstance(friend_data, str):
                        friend_user_id = str(friend_data)
                    else:
                        continue
                    
                    print(f"🔍 Processing friend: {friend_user_id}")
                    
                    friend_found = False
                    actual_friend_id = None
                    
                    for acc_key in accounts.keys():
                        if str(acc_key) == str(friend_user_id):
                            actual_friend_id = acc_key
                            friend_found = True
                            break
                    
                    if not friend_found:
                        print(f"❌ Friend {friend_user_id} not found in accounts")
                        continue
                    
                    if actual_friend_id and actual_friend_id in accounts:
                        friend_accounts_data = accounts[actual_friend_id]
                        if not isinstance(friend_accounts_data, dict):
                            continue
                            
                        friend_accounts = friend_accounts_data.get("accounts", [])
                        if not friend_accounts:
                            continue
                            
                        friend_api_id = friend_accounts[0].get('api_user_id') if friend_accounts else None
                        friend_username = friend_accounts[0].get('username', 'Unknown') if friend_accounts else 'Unknown'
                        friend_telegram_username = friend_accounts[0].get('telegram_username', '') if friend_accounts else ''
                        
                        # ফ্রেন্ডের জন্য supervisor হিসেবে বর্তমান ইউজারকে সেট করা
                        user_under_supervisors[actual_friend_id] = {
                            'name': username,
                            'telegram_username': telegram_username,
                            'user_id': user_id_str
                        }
                        
                        print(f"✅ Processing friend: {friend_username} (API: {friend_api_id})")
                        
                        # ফ্রেন্ডের settlement ডেটা fetch করা
                        friend_token = None
                        
                        try:
                            for acc in friend_accounts:
                                if acc.get('token'):
                                    async with aiohttp.ClientSession() as token_session:
                                        status_code, _, _ = await get_status_async(token_session, acc['token'], "0000000000")
                                    if status_code != -1:
                                        friend_token = acc['token']
                                        break
                        except:
                            pass
                        
                        if not friend_token:
                            for acc in friend_accounts:
                                if acc.get('active', True):
                                    token, api_id, nickname = await login_api_async(acc['username'], acc['password'])
                                    if token:
                                        friend_token = token
                                        acc['token'] = token
                                        if api_id:
                                            acc['api_user_id'] = api_id
                                        acc['nickname'] = nickname
                                        acc['last_login'] = datetime.now().isoformat()
                                        break
                        
                        if friend_token and friend_api_id:
                            try:
                                async with aiohttp.ClientSession() as friend_session:
                                    friend_settlement_data, error = await get_user_settlements(
                                        friend_session, friend_token, str(friend_api_id), page=1, page_size=100
                                    )
                                    
                                    if error:
                                        print(f"❌ Error fetching friend settlements: {error}")
                                        continue
                                    
                                    if friend_settlement_data and friend_settlement_data.get('records'):
                                        friend_filtered_count = 0
                                        friend_countries = []
                                        friend_earnings = 0
                                        
                                        for record in friend_settlement_data.get('records', []):
                                            gmt_create = record.get('gmtCreate')
                                            if not gmt_create:
                                                continue
                                            
                                            try:
                                                if 'T' in gmt_create:
                                                    record_date = datetime.fromisoformat(gmt_create.replace('Z', '+00:00')).date()
                                                else:
                                                    record_date = datetime.strptime(gmt_create, '%Y-%m-%d %H:%M:%S').date()
                                                
                                                if record_date != target_date:
                                                    continue
                                                
                                                country = record.get('countryName') or record.get('country') or 'Unknown'
                                                
                                                # Check country filter
                                                if country_rates:
                                                    country_matched = False
                                                    matched_country = None
                                                    
                                                    for target_country in country_rates.keys():
                                                        if target_country.lower() in country.lower() or country.lower() in target_country.lower():
                                                            country_matched = True
                                                            matched_country = target_country
                                                            break
                                                    
                                                    if not country_matched:
                                                        continue
                                                # If no country rates specified, use default rate
                                                elif not default_rate:
                                                    continue
                                                
                                                count = record.get('count', 0)
                                                friend_filtered_count += count
                                                
                                                # Calculate earnings based on country rates
                                                if country_rates:
                                                    # Find matching country rate
                                                    rate = default_rate
                                                    for target_country, target_rate in country_rates.items():
                                                        if target_country.lower() in country.lower() or country.lower() in target_country.lower():
                                                            rate = target_rate
                                                            break
                                                else:
                                                    rate = default_rate
                                                
                                                friend_earnings += count * rate
                                                
                                                if country not in friend_countries:
                                                    friend_countries.append(country)
                                                    
                                            except Exception as e:
                                                continue
                                        
                                        print(f"📈 Friend {friend_username} filtered count for target countries: {friend_filtered_count}")
                                        
                                        if friend_filtered_count >= 10:
                                            friend_commission = friend_filtered_count * commission_rate
                                            total_commission += friend_commission
                                            total_friend_counts += friend_filtered_count
                                            total_eligible_friends += 1
                                            
                                            friend_name = "Unknown"
                                            if isinstance(friend_data, dict) and 'name' in friend_data:
                                                friend_name = friend_data['name']
                                            elif friend_accounts and friend_accounts[0].get('nickname'):
                                                friend_name = friend_accounts[0].get('nickname')
                                            elif friend_accounts and friend_accounts[0].get('username'):
                                                friend_name = friend_accounts[0].get('username')
                                            
                                            friends_details.append({
                                                'name': friend_name,
                                                'username': friend_username,
                                                'telegram_username': friend_telegram_username,
                                                'accounts': len(friend_accounts),
                                                'counts': friend_filtered_count,
                                                'commission': friend_commission,
                                                'countries': friend_countries,
                                                'earnings': friend_earnings,
                                                'friend_user_id': actual_friend_id
                                            })
                                            
                                            print(f"✅ Friend commission added: {friend_name} - ${friend_commission:.2f} from {friend_filtered_count} counts")
                                        else:
                                            print(f"⚠️ Friend {friend_username} has only {friend_filtered_count} counts in target countries (needs 10)")
                                    else:
                                        print(f"⚠️ No settlement records found for friend {friend_username}")
                            except Exception as e:
                                print(f"❌ Friend calculation error: {type(e).__name__}: {e}")
                                continue
                
                # ৩. এখন টোটাল ক্যালকুলেশন করা
                total_usd_with_commission = total_usd_user + total_commission
                total_bdt_user = total_usd_with_commission * USD_TO_BDT
                
                print(f"💰 Final calculation for {username}:")
                print(f"  Personal: ${total_usd_user:.2f}")
                print(f"  Commission: ${total_commission:.2f}")
                print(f"  Total USD: ${total_usd_with_commission:.2f}")
                print(f"  Total BDT: {total_bdt_user:.2f}")
                
                if total_commission > 0 and total_count == 0:
                    users_with_only_commission += 1
                    print(f"👥 User {username} has only commission: ${total_commission:.2f}")
                
                # Check if user has any earnings
                has_earnings = total_usd_user > 0 or total_commission > 0
                
                if has_earnings:
                    users_with_earnings += 1
                else:
                    users_without_earnings += 1
                    print(f"ℹ️ User {username} has no earnings, skipping from report")
                    continue
                
                user_summary = {
                    'user_id': user_id_str,
                    'username': username,
                    'telegram_username': telegram_username,
                    'api_user_id': api_user_id,
                    'settlement_date': target_date_display,
                    'countries': list(country_totals.keys()),
                    'country_totals': country_totals,
                    'total_count': total_count,
                    'personal_usd': total_usd_user,
                    'total_commission': total_commission,
                    'friends_details': friends_details,
                    'total_usd': total_usd_with_commission,
                    'total_bdt': total_bdt_user,
                    'num_records': len(user_filtered_settlements),
                    'token_refreshed': token_refreshed,
                    'has_personal_settlement': len(user_filtered_settlements) > 0,
                    'friend_counts': sum(f['counts'] for f in friends_details),
                    'total_counts': total_count + sum(f['counts'] for f in friends_details),
                    'has_earnings': has_earnings
                }
                
                all_users_summary.append(user_summary)
                total_users += 1
                total_usd += total_usd_with_commission
                total_bdt += total_bdt_user
                
                print(f"✅ User {username} added to summary")
                
            except Exception as e:
                print(f"❌ User {user_id_str} processing error: {type(e).__name__}: {e}")
                users_failed += 1
                continue
        
        # Update settings with the first rate (for backward compatibility)
        if default_rate:
            settings['settlement_rate'] = default_rate
        elif country_rates:
            # Store first country rate as default
            first_country = list(country_rates.keys())[0]
            settings['settlement_rate'] = country_rates[first_country]
        
        settings['last_updated'] = datetime.now().isoformat()
        settings['updated_by'] = ADMIN_ID
        save_settings(settings)
        
        print(f"\n📈 Processing complete:")
        print(f"• Total users processed: {users_processed}")
        print(f"• Users with earnings: {users_with_earnings}")
        print(f"• Users without earnings: {users_without_earnings}")
        print(f"• Users with settlements: {users_with_settlements}")
        print(f"• Users with only commission: {users_with_only_commission}")
        print(f"• Total friends in system: {total_friends_count}")
        print(f"• Eligible friends (10+ counts): {total_eligible_friends}")
        print(f"• Total personal counts: {total_personal_count}")
        print(f"• Total friend counts: {total_friend_counts}")
        print(f"• Grand total counts: {total_personal_count + total_friend_counts}")
        print(f"• Total commission: ${sum(u['total_commission'] for u in all_users_summary):.2f}")
        print(f"• Total USD: ${total_usd:.2f}")
        print(f"• Total BDT: {total_bdt:.2f}")
        
        notified_users = 0
        for user_summary in all_users_summary:
            try:
                # চেক করা যে এই ইউজার কারো অধীনে কাজ করছে কিনা
                supervisor_info = None
                if user_summary['user_id'] in user_under_supervisors:
                    supervisor_info = user_under_supervisors[user_summary['user_id']]
                
                # Get rate for this user (for display)
                display_rate = default_rate if default_rate else list(country_rates.values())[0]
                
                message = "✨ Settlement Rate Update ✨\n\n"
                message += "📢 Notification for Your Account\n\n"
                
                message += "📋 Details:\n"
                message += f"• 📅 Date: {user_summary['settlement_date']}\n"
                
                if country_rates:
                    if len(country_rates) == 1:
                        country = list(country_rates.keys())[0]
                        rate = country_rates[country]
                        message += f"• 🌍 Country: {country} only\n"
                        message += f"• 💰 Base Rate: ${rate:.3f} per count\n"
                    else:
                        message += f"• 🌍 Countries & Rates:\n"
                        for country, rate in country_rates.items():
                            message += f"  • {country}: ${rate:.3f}/count\n"
                else:
                    message += f"• 🌍 Countries: All countries\n"
                    message += f"• 💰 Base Rate: ${display_rate:.3f} per Account\n\n"
                
                
                message += "\n📊 Your Performance:\n"
                message += f"• Your Account: {user_summary['total_count']} counts\n"
                message += f"• Your USD: ${user_summary['personal_usd']:.2f} ({user_summary['total_count']} × ${display_rate:.3f})\n\n"
                
                # ফ্রেন্ড কমিশন থাকলে
                if user_summary['friends_details']:
                    message += "👥 Your Friends Performance (min 10 counts required):\n"
                    
                    # Split friends into chunks of 10
                    friends_chunks = [user_summary['friends_details'][i:i+10] for i in range(0, len(user_summary['friends_details']), 10)]
                    
                    for chunk_num, friends_chunk in enumerate(friends_chunks, 1):
                        if chunk_num > 1:
                            message += f"\n📋 Friends List (Part {chunk_num}):\n"
                        
                        for i, friend in enumerate(friends_chunk, start=(chunk_num-1)*10 + 1):
                            telegram_username_display = f" ({friend['telegram_username']})" if friend['telegram_username'] else ""
                            friend_earned = friend['earnings']
                            friend_earned_bdt = friend_earned * USD_TO_BDT
                            
                            message += f"{i}. {friend['name']}{telegram_username_display}\n"
                            message += f"   • Accounts: {friend['accounts']}\n"
                            
                            if friend['countries']:
                                if len(friend['countries']) == 1:
                                    message += f"   • Counts: {friend['counts']} ({friend['countries'][0]}: {friend['counts']})\n"
                                else:
                                    message += f"   • Counts: {friend['counts']} ({', '.join(friend['countries'])})\n"
                            else:
                                message += f"   • Counts: {friend['counts']}\n"
                            
                            message += f"   • Earned: ${friend_earned:.2f}/{friend_earned_bdt:.0f} BDT\n"
                            message += f"   • Commission: ${friend['commission']:.2f} ({friend['counts']} × ${commission_rate:.3f})\n\n"
                    
                    message += f"💸 Total Commission from Friends: ${user_summary['total_commission']:.2f}\n\n"
                    
                    # Count summary
                    message += "📈 Count Summary:\n"
                    message += f"• Your Counts: {user_summary['total_count']}\n"
                    message += f"• Friends Counts: {user_summary['friend_counts']}\n"
                    message += f"• Total Counts: {user_summary['total_counts']}\n\n"
                else:
                    message += "👥 Your Network:\n"
                    message += f"• Friends: 0 users\n\n"
                
                # Calculate friend earnings (not commission)
                friend_earnings = sum(f['earnings'] for f in user_summary['friends_details'])

                # Total calculation summary
                message += "💰 Earnings Summary:\n"
                message += f"• Personal Earnings: ${user_summary['personal_usd']:.2f}\n"
                message += f"• All Friends Earned: ${friend_earnings:.2f}\n\n"
                
                # Calculate total (Personal + All Friends + Commission)
                total_all_earnings = user_summary['personal_usd'] + friend_earnings + user_summary['total_commission']
                total_all_bdt = total_all_earnings * USD_TO_BDT

                message += f"• Total USD: ${total_all_earnings:.2f}\n"
                message += f"• Total BDT: {total_all_bdt:.2f} BDT\n\n"
                
                # যদি এই ইউজার কারো অধীনে কাজ করে
                if supervisor_info:
                    supervisor_name = supervisor_info['name']
                    supervisor_telegram = supervisor_info['telegram_username']
                    supervisor_display = f" ({supervisor_telegram})" if supervisor_telegram else ""
                    message += f"👤 Your Friend: {supervisor_name}{supervisor_display}\n\n"
                
                
                
                await context.bot.send_message(
                    int(user_summary['user_id']),
                    message,
                    parse_mode='none'
                )
                notified_users += 1
                await asyncio.sleep(1)
                
                print(f"📨 Notification sent to {user_summary['username']}")
                
            except Exception as e:
                print(f"❌ Notification failed for {user_summary['user_id']}: {e}")
        
        # Only send admin report if there are users with earnings
        if all_users_summary:
            # এখন টোটাল স্ট্যাটিসটিক্স ক্যালকুলেশন করা
            total_personal_usd = sum(u['personal_usd'] for u in all_users_summary)
            total_commissions = sum(u['total_commission'] for u in all_users_summary)
            total_eligible_friends_in_summary = sum(len([f for f in u['friends_details'] if f['counts'] >= 10]) for u in all_users_summary)
            total_user_friend_counts = sum(u['friend_counts'] for u in all_users_summary)
            grand_total_counts = total_personal_count + total_friend_counts
            
            # Calculate total friend earnings for all users
            total_friend_earnings = sum(
                sum(f['earnings'] for f in u['friends_details']) 
                for u in all_users_summary
            )

            # Total all earnings (Personal + All Friends + Commission)
            total_all_earnings = total_personal_usd + total_friend_earnings + total_commissions
            total_all_bdt = total_all_earnings * USD_TO_BDT
            
            # ডিটেইলড সামারি মেসেজ
            detailed_summary = "📊 DETAILED SETTLEMENT SUMMARY 📊\n\n"
            
            detailed_summary += "📅 Date: " + target_date_display + "\n"
            
            if country_rates:
                if len(country_rates) == 1:
                    country = list(country_rates.keys())[0]
                    rate = country_rates[country]
                    detailed_summary += f"💰 Rate: ${rate:.2f} per count ({country})\n"
                else:
                    detailed_summary += f"💰 Rates by Country:\n"
                    for country, rate in country_rates.items():
                        detailed_summary += f"• {country}: ${rate:.3f}/count\n"
            else:
                detailed_summary += f"💰 Rate: ${default_rate:.2f} per count (All countries)\n"
            
            detailed_summary += f"👥 Commission Rate: ${commission_rate:.3f} per count\n"
            detailed_summary += f"💱 Exchange Rate: 1 USD = {USD_TO_BDT} BDT\n\n"
            
            detailed_summary += "📈 USER STATISTICS:\n"
            detailed_summary += f"• 👥 Total Users: {total_users} (with earnings)\n"
            detailed_summary += f"• 👥 Skipped Users: {users_without_earnings} (no earnings)\n"
            detailed_summary += f"• ✅ Users with Personal Settlements: {users_with_settlements}\n"
            detailed_summary += f"• 👥 Users with Only Commission: {users_with_only_commission}\n"
            detailed_summary += f"• 🔄 Auto-Refreshed Accounts: {users_token_refreshed}\n"
            detailed_summary += f"• ❌ Failed Users: {users_failed}\n"
            detailed_summary += f"• 📨 Notifications Sent: {notified_users}\n\n"
            
            detailed_summary += "📊 COUNT SUMMARY:\n"
            detailed_summary += f"• 🔢 Total Personal Counts: {total_personal_count}\n"
            detailed_summary += f"• 👥 Total Friend Counts: {total_friend_counts}\n"
            detailed_summary += f"• 📈 Grand Total Counts: {grand_total_counts} ({total_personal_count} + {total_friend_counts})\n\n"
            
            detailed_summary += "🤝 FRIEND NETWORK:\n"
            detailed_summary += f"• 👥 Total Friends in System: {total_friends_count}\n"
            detailed_summary += f"• ✅ Eligible Friends (10+ counts): {total_eligible_friends_in_summary}\n"
            detailed_summary += f"• 🔢 Total Eligible Friend Counts: {total_friend_counts}\n\n"
            
            detailed_summary += "💰 FINANCIAL SUMMARY:\n"
            detailed_summary += f"• 💵 Personal Earnings: ${total_personal_usd:.2f} ({total_personal_count} × rate)\n"
            detailed_summary += f"• 👥 All Friends Earned: ${total_friend_earnings:.2f} ({total_friend_counts} × rate)\n"
            detailed_summary += f"• 💸 Total Commission: ${total_commissions:.2f} ({total_friend_counts} × ${commission_rate:.3f})\n"
            detailed_summary += f"• 📊 Total (Personal+Friends+Commission): ${total_all_earnings:.2f}\n"
            detailed_summary += f"• 🇧🇩 Total BDT: {total_all_bdt:.2f} (${total_all_earnings:.2f} × {USD_TO_BDT})\n"
            detailed_summary += f"• 📊 Total Records: {sum(u['num_records'] for u in all_users_summary)}\n\n"
            
            detailed_summary += "📋 AVERAGE PER USER:\n"
            if total_users > 0:
                avg_personal = total_personal_usd / total_users
                avg_commission = total_commissions / total_users
                avg_total = total_usd / total_users
                avg_personal_counts = total_personal_count / total_users
                avg_friend_counts = total_friend_counts / total_users
                
                detailed_summary += f"• 🔢 Avg Personal Counts: {avg_personal_counts:.1f}\n"
                detailed_summary += f"• 👥 Avg Friend Counts: {avg_friend_counts:.1f}\n"
                detailed_summary += f"• 💵 Avg Base Earnings: ${avg_personal:.2f}\n"
                detailed_summary += f"• 👥 Avg Commission: ${avg_commission:.2f}\n"
                detailed_summary += f"• 💰 Avg Total Earnings: ${avg_total:.2f}\n\n"
            
            detailed_summary += "✅ OPERATION SUCCESSFUL!\n"
            detailed_summary += "All payments have been calculated and notifications sent.\n\n"
            detailed_summary += f"⏰ Completed at: {datetime.now().strftime('%H:%M:%S')}"
            
            await processing_msg.edit_text(detailed_summary, parse_mode='none')
            
            # অ্যাডমিনের জন্য ডিটেইলড রিপোর্ট
            users_per_message = 5
            total_chunks = (len(all_users_summary) + users_per_message - 1) // users_per_message
            
            for chunk_index in range(total_chunks):
                start_idx = chunk_index * users_per_message
                end_idx = min(start_idx + users_per_message, len(all_users_summary))
                chunk = all_users_summary[start_idx:end_idx]
                
                details_message = f"📋 USER DETAILS - PART {chunk_index + 1}/{total_chunks} 📋\n\n"
                
                for i, user_summary in enumerate(chunk, start=start_idx + 1):
                    refresh_icon = " 🔄" if user_summary['token_refreshed'] else ""
                    settlement_icon = " ✅" if user_summary['has_personal_settlement'] else " 👥"
                    telegram_display = f" ({user_summary['telegram_username']})" if user_summary['telegram_username'] else ""
                    
                    details_message += f"{i}. {user_summary['username']}{telegram_display} (ID: {user_summary['api_user_id']}){refresh_icon}{settlement_icon}\n"
                    details_message += f"   ├─ 👤 API ID: {user_summary['api_user_id']}\n"
                    
                    user_data = accounts.get(user_summary['user_id'], {})
                    user_accounts_count = len(user_data.get("accounts", [])) if isinstance(user_data, dict) else 0
                    details_message += f"   ├─ 👥 Accounts: {user_accounts_count}\n"
                    
                    if len(user_summary['countries']) == 1:
                        details_message += f"   ├─ 🌍 Country: {user_summary['countries'][0]}\n"
                    elif len(user_summary['countries']) > 1:
                        details_message += f"   ├─ 🌍 Countries: {', '.join(user_summary['countries'])}\n"
                    else:
                        details_message += f"   ├─ 🌍 Countries: All\n"
                    
                    details_message += f"   ├─ 🔢 Personal Count: {user_summary['total_count']}\n"
                    details_message += f"   ├─ 💰 Base Earnings: ${user_summary['personal_usd']:.2f}\n"
                    
                    if user_summary['friends_details']:
                        details_message += f"   ├─ 🤝 Total Friends: {len(user_summary['friends_details'])} ({len([f for f in user_summary['friends_details'] if f['counts'] >= 10])} eligible)\n"
                        
                        for j, friend in enumerate(user_summary['friends_details'], 1):
                            friend_telegram_display = f" ({friend['telegram_username']})" if friend['telegram_username'] else ""
                            friend_earned = friend['earnings']
                            friend_earned_bdt = friend_earned * USD_TO_BDT
                            
                            details_message += f"   ├─ 👤 Friend {j}: {friend['name']}{friend_telegram_display}\n"
                            details_message += f"   ├─   ├─ 📱 Accounts: {friend['accounts']}\n"
                            details_message += f"   ├─   ├─ 🔢 Counts: {friend['counts']} "
                            if friend['counts'] >= 10:
                                details_message += "✅\n"
                            else:
                                details_message += "❌\n"
                            
                            details_message += f"   ├─   ├─ 💰 Earned: ${friend_earned:.2f}/{friend_earned_bdt:.0f}bdt\n"
                            
                            if friend['countries']:
                                details_message += f"   ├─   ├─ 🌍 Countries: {', '.join(friend['countries'])}\n"
                            
                            details_message += f"   ├─   └─ 💸 Commission: ${friend['commission']:.2f}\n"
                    else:
                        details_message += f"   ├─ 🤝 Total Friends: 0 (0 eligible)\n"
                    
                    # Calculate friend earnings for this user
                    friend_earnings = sum(f['earnings'] for f in user_summary['friends_details'])
                    total_all_earnings_user = user_summary['personal_usd'] + friend_earnings + user_summary['total_commission']
                    total_all_bdt_user = total_all_earnings_user * USD_TO_BDT
                    
                    # কাউন্ট সামারি
                    details_message += f"   ├─ 📊 Count Summary:\n"
                    details_message += f"   ├─   ├─ 🔢 Your Counts: {user_summary['total_count']}\n"
                    details_message += f"   ├─   ├─ 👥 Friend Counts: {user_summary['friend_counts']}\n"
                    details_message += f"   ├─   └─ 📈 Total Counts: {user_summary['total_counts']}\n"
                    
                    details_message += f"   ├─ 💰 Personal Earnings: ${user_summary['personal_usd']:.2f}\n"
                    details_message += f"   ├─ 👥 All Friends Earned: ${friend_earnings:.2f}\n"
                    details_message += f"   ├─ 💸 Total Commission: ${user_summary['total_commission']:.2f}\n"
                    details_message += f"   ├─ 📊 Total (P+F+C): ${total_all_earnings_user:.2f}\n"
                    details_message += f"   └─ 🇧🇩 Total BDT: {total_all_bdt_user:.2f}\n\n"
                
                chunk_personal_counts = sum(u['total_count'] for u in chunk)
                chunk_friend_counts = sum(u['friend_counts'] for u in chunk)
                chunk_total_counts = sum(u['total_counts'] for u in chunk)
                chunk_personal_usd = sum(u['personal_usd'] for u in chunk)
                chunk_friend_earnings = sum(sum(f['earnings'] for f in u['friends_details']) for u in chunk)
                chunk_commission = sum(u['total_commission'] for u in chunk)
                chunk_total = sum(u['total_usd'] for u in chunk)
                chunk_total_all = chunk_personal_usd + chunk_friend_earnings + chunk_commission
                chunk_bdt = chunk_total_all * USD_TO_BDT
                
                details_message += f"📊 Chunk {chunk_index + 1} Total:\n"
                details_message += f"• 👥 Users: {len(chunk)}\n"
                details_message += f"• 🔢 Personal Counts: {chunk_personal_counts}\n"
                details_message += f"• 👥 Friend Counts: {chunk_friend_counts}\n"
                details_message += f"• 📈 Total Counts: {chunk_total_counts}\n"
                details_message += f"• 💵 Personal USD: ${chunk_personal_usd:.2f}\n"
                details_message += f"• 👥 Friends Earned: ${chunk_friend_earnings:.2f}\n"
                details_message += f"• 💸 Commission: ${chunk_commission:.2f}\n"
                details_message += f"• 💰 Total (P+F+C): ${chunk_total_all:.2f}\n"
                details_message += f"• 🇧🇩 Total BDT: {chunk_bdt:.2f}\n\n"
                
                if chunk_index < total_chunks - 1:
                    details_message += "⬇️ More details in next message..."
                
                try:
                    await context.bot.send_message(
                        ADMIN_ID,
                        details_message,
                        parse_mode='none'
                    )
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"❌ Error sending chunk {chunk_index + 1}: {e}")
            
        else:
            summary_message = "🎯 Settlement Rate Update Complete 🎯\n\n"
            
            summary_message += "📊 Operation Summary:\n"
            summary_message += f"• 📅 Target Date: {target_date_display}\n"
            
            if country_rates:
                if len(country_rates) == 1:
                    country = list(country_rates.keys())[0]
                    rate = country_rates[country]
                    summary_message += f"• 🌍 Country: {country} (${rate:.3f}/count)\n"
                else:
                    summary_message += f"• 🌍 Countries & Rates:\n"
                    for country, rate in country_rates.items():
                        summary_message += f"  • {country}: ${rate:.3f}/count\n"
            else:
                summary_message += f"• 🔄 Previous Rate: ${old_rate:.2f}\n"
                summary_message += f"• ✅ New Rate: ${default_rate:.2f}\n"
            
            summary_message += f"\n📈 Processing Statistics:\n"
            summary_message += f"• 👥 Total Users: {users_processed}\n"
            summary_message += f"• ✅ Users with Earnings: {users_with_earnings}\n"
            summary_message += f"• 👥 Users without Earnings: {users_without_earnings}\n"
            summary_message += f"• 🔄 Auto-Refreshed: {users_token_refreshed}\n"
            summary_message += f"• ❌ Failed: {users_failed}\n\n"
            
            summary_message += f"📭 No settlements found for {target_date_display} with the specified criteria\n"
            
            if default_rate:
                summary_message += f"ℹ️ Rate Updated: ${default_rate:.2f} (for future settlements)\n\n"
            
            summary_message += f"⏰ Completed at: {datetime.now().strftime('%H:%M:%S')}"
            
            await processing_msg.edit_text(summary_message, parse_mode='none')
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid Command Format!\n\n"
            "📝 Usage: `/setrate [country_rate_pairs] [date]`\n"
            "📢 Notice: `/setrate notice Your message`\n\n"
            "✅ Examples:\n"
            "• `/setrate 0.08`\n"
            "• `/setrate 0.07 canada 0.04 benin 0.09 nigeria`\n"
            "• `/setrate 0.07 canada 0.04 benin 2/12`\n"
            "• `/setrate notice Payment tomorrow`"
        )

async def admin_add_account(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
        
    if not context.args or len(context.args) < 3:
        await update.message.reply_text("❌ Usage: `/addacc user_id username password`\nExample: `/addacc 123456789 user1 pass1`")
        return
        
    try:
        target_user_id = context.args[0]
        username = context.args[1]
        password = context.args[2]
        
        processing_msg = await update.message.reply_text(f"🔄 Verifying account `{username}`...")
        token, api_user_id, nickname = await login_api_async(username, password)
        
        if not token:
            await processing_msg.edit_text(f"❌ Login failed for `{username}`! Please check credentials.")
            return
            
        accounts = load_accounts()
        user_id_str = str(target_user_id)
        
        if user_id_str not in accounts:
            accounts[user_id_str] = {
                "accounts": [],
                "selected_account_id": 1,
                "telegram_username": "",
                "last_active": datetime.now().isoformat()
            }
        
        user_data = accounts[user_id_str]
        if not isinstance(user_data, dict):
            user_data = {
                "accounts": [],
                "selected_account_id": 1,
                "telegram_username": "",
                "last_active": datetime.now().isoformat()
            }
        
        account_exists = False
        for acc in user_data.get("accounts", []):
            if acc['username'] == username:
                acc['password'] = password
                acc['token'] = token
                acc['api_user_id'] = api_user_id
                acc['nickname'] = nickname
                acc['last_login'] = datetime.now().isoformat()
                acc['active'] = True
                account_exists = True
                break
        
        if not account_exists:
            new_id = len(user_data.get("accounts", [])) + 1
            user_data["accounts"].append({
                'id': new_id,
                'custom_name': username,
                'username': username,
                'password': password,
                'token': token,
                'api_user_id': api_user_id,
                'nickname': nickname,
                'last_login': datetime.now().isoformat(),
                'active': True,
                'default': (new_id == 1),
                'added_by': update.effective_user.id,
                'added_at': datetime.now().isoformat(),
                'telegram_username': '',
                'friends': []  # Add friends field
            })
        
        accounts[user_id_str] = user_data
        save_accounts(accounts)
        
        if user_id_str in account_manager.user_tokens:
            await account_manager.initialize_user(int(target_user_id))
        
        await processing_msg.edit_text(
            f"✅ Account added successfully!\n\n"
            f"👤 User ID: `{target_user_id}`\n"
            f"📛 Username: `{username}`\n"
            f"🔑 Password: `{password}`\n"
            f"🆔 API User ID: `{api_user_id or 'N/A'}`\n"
            f"✅ Auto-login: Successful"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def admin_remove_account(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
        
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❌ Usage: `/removeacc user_id username`\nExample: `/removeacc 123456789 user1`")
        return
        
    try:
        target_user_id = context.args[0]
        username = context.args[1]
        
        accounts = load_accounts()
        user_id_str = str(target_user_id)
        
        user_data = accounts.get(user_id_str, {})
        if not isinstance(user_data, dict):
            await update.message.reply_text(f"❌ No accounts found for user `{target_user_id}`")
            return
        
        removed = False
        new_accounts = []
        for acc in user_data.get("accounts", []):
            if acc['username'] == username:
                removed = True
                if acc.get('token') and acc['token'] in account_manager.token_info:
                    del account_manager.token_info[acc['token']]
                if acc.get('token') and acc['token'] in account_manager.token_owners:
                    del account_manager.token_owners[acc['token']]
            else:
                new_accounts.append(acc)
        
        if removed:
            user_data["accounts"] = new_accounts
            accounts[user_id_str] = user_data
            save_accounts(accounts)
            
            if user_id_str in account_manager.user_tokens:
                account_manager.user_tokens[user_id_str] = [
                    token for token in account_manager.user_tokens[user_id_str] 
                    if token not in account_manager.token_info
                ]
            
            await update.message.reply_text(
                f"✅ Account removed successfully!\n\n"
                f"👤 User ID: `{target_user_id}`\n"
                f"📛 Username: `{username}`"
            )
        else:
            await update.message.reply_text(f"❌ Account `{username}` not found for user `{target_user_id}`")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def admin_list_accounts(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
        
    accounts = load_accounts()
    
    if not accounts:
        await update.message.reply_text("❌ No accounts in database!")
        return
    
    message = "📋 All User Accounts 👑\n\n"
    
    for user_id_str, user_data in accounts.items():
        if not isinstance(user_data, dict):
            continue
            
        user_accounts = user_data.get("accounts", [])
        message += f"👤 User ID: {user_id_str}\n"
        message += f"📊 Total Accounts: {len(user_accounts)}\n"
        
        active_accounts = len([acc for acc in user_accounts if acc.get('active', True)])
        logged_in_accounts = account_manager.get_user_active_accounts_count(int(user_id_str))
        
        message += f"✅ Active: {active_accounts} | 🔓 Logged In: {logged_in_accounts}\n"
        
        for i, acc in enumerate(user_accounts, 1):
            status = "✅" if acc.get('active', True) else "❌"
            login_status = "🔓" if acc.get('token') else "🔒"
            nickname = acc.get('nickname', 'N/A')
            api_user_id = acc.get('api_user_id', 'N/A')
            message += f"  {i}. {status}{login_status} {acc['username']} ({nickname}) [ID: {api_user_id[:8] if api_user_id != 'N/A' else 'N/A'}]\n"
        
        message += "───\n"
    
    await update.message.reply_text(message)

async def handle_settlement_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith('settlement_'):
        if data.startswith('settlement_refresh_'):
            page = int(data.split('_')[2])
        else:
            page = int(data.split('_')[1])
        
        user_id = query.from_user.id
        user_id_str = str(user_id)
        
        if user_id_str not in account_manager.user_tokens or not account_manager.user_tokens[user_id_str]:
            await query.edit_message_text("❌ No active accounts found!")
            return
        
        token = account_manager.user_tokens[user_id_str][0]
        
        api_user_id = account_manager.get_api_user_id_for_token(token)
        
        if not api_user_id:
            await query.edit_message_text(
                "❌ Could not find your API user ID.\n\n"
                "Please refresh your accounts by clicking '🚀 Refresh Server' button first."
            )
            return
        
        async with aiohttp.ClientSession() as session:
            data_result, error = await get_user_settlements(session, token, str(api_user_id), page=page, page_size=5)
        
        if error:
            await query.edit_message_text(f"❌ Error loading settlements: {error}")
            return
        
        if not data_result or not data_result.get('records'):
            await query.edit_message_text("❌ No settlement records found for your account!")
            return
        
        records = data_result.get('records', [])
        total_records = data_result.get('total', 0)
        total_pages = data_result.get('pages', 1)
        
        total_count = 0
        total_amount = 0
        for record in records:
            count = record.get('count', 0)
            record_rate = record.get('receiptPrice', 0.10)
            total_count += count
            total_amount += count * record_rate
        
        message = f"📦 Your Settlement Records\n\n"
        message += f"📊 Total Records: {total_records}\n"
        message += f"🔢 Total Count: {total_count}\n"
        message += f"📄 Page: {page}/{total_pages}\n\n"
        
        for i, record in enumerate(records, 1):
            record_id = record.get('id', 'N/A')
            if record_id != 'N/A' and len(str(record_id)) > 8:
                record_id = str(record_id)[:8] + '...'
            
            count = record.get('count', 0)
            record_rate = record.get('receiptPrice', 0.10)
            amount = count * record_rate
            gmt_create = record.get('gmtCreate', 'N/A')
            country = record.get('countryName', 'N/A') or record.get('country', 'N/A')
            
            try:
                if gmt_create != 'N/A':
                    if 'T' in gmt_create:
                        date_obj = datetime.fromisoformat(gmt_create.replace('Z', '+00:00'))
                    else:
                        date_obj = datetime.strptime(gmt_create, '%Y-%m-%d %H:%M:%S')
                    formatted_date = date_obj.strftime('%d %B %Y, %H:%M')
                else:
                    formatted_date = 'N/A'
            except:
                formatted_date = gmt_create
            
            message += f"{i}. Settlement #{record_id}\n"
            message += f"📅 Date: {formatted_date}\n"
            message += f"🌍 Country: {country}\n"
            message += f"🔢 Count: {count}\n"
            
        
        keyboard = []
        row = []
        
        if page > 1:
            row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"settlement_{page-1}"))
        
        if page < total_pages:
            if not row:
                row = []
            row.append(InlineKeyboardButton("Next ➡️", callback_data=f"settlement_{page+1}"))
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data=f"settlement_refresh_{page}")])
        
        if keyboard:
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='none')
        else:
            await query.edit_message_text(message, parse_mode='none')

async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    try:
        user = update.effective_user
        user_info = f"""
🆕 New User Started Bot 🆕

👤 Full Name: {user.full_name or 'N/A'}
🆔 User ID: `{user.id}`
📛 Username: @{user.username if user.username else 'N/A'}
📅 Date: {datetime.now().strftime('%d %B %Y, %H:%M:%S')}
        """
        
        await context.bot.send_message(
            chat_id="@userupdate4209",
            text=user_info,
            parse_mode='none'
        )
    except Exception as e:
        print(f"⚠️ Failed to send user info to group: {e}")
    
    active_accounts = await account_manager.initialize_user(user_id)
    
    if user_id == ADMIN_ID:
        keyboard = [
            [KeyboardButton("➕ Add Account"), KeyboardButton("📋 List Accounts")],
            [KeyboardButton("🚀 Refresh Server"), KeyboardButton("💰 Set Rate")],
            [KeyboardButton("📊 Statistics"), KeyboardButton("📱 Switch Account")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        remaining = account_manager.get_user_remaining_checks(user_id)
        active_accounts_count = account_manager.get_user_active_accounts_count(user_id)
        selected_account = account_manager.get_selected_account_name(user_id)
        
        await update.message.reply_text(
            f"🔥 WA OTP 👑\n\n"
            f"📱 Active Account: {selected_account}\n"
            f"✅ Active Login: {active_accounts_count}\n"
            f"🎯 Remaining Checks: {remaining}\n\n"
            f"💡 OTP Tip: Reply to any 'In Progress' number with OTP code",
            reply_markup=reply_markup
        )
        return
        
    keyboard = [
        [KeyboardButton("🚀 Refresh Server"), KeyboardButton("📱 Switch Account")],
        [KeyboardButton("📦 My Settlements"), KeyboardButton("📊 Statistics")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    remaining = account_manager.get_user_remaining_checks(user_id)
    active_accounts_count = account_manager.get_user_active_accounts_count(user_id)
    selected_account = account_manager.get_selected_account_name(user_id)
    
    if active_accounts == 0:
        await update.message.reply_text(
            f"❌ Access Denied!\n\n"
            f"Please contact admin for access.\n"
            f"Admin: @Notfound_errorx",
            reply_markup=reply_markup
        )
        return
    
    await update.message.reply_text(
        f"🔥 WA OTP\n\n"
        f"📱 Active Account: {selected_account}\n"
        f"✅ Active Login: {active_accounts_count}\n"
        f"🎯 Remaining Checks: {remaining}\n\n"
        f"💡 OTP Tip: Reply to any 'In Progress' number with OTP code",
        reply_markup=reply_markup
    )

async def show_accounts_menu(update: Update, context: CallbackContext):
    """Show accounts selection menu"""
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    
    accounts = load_accounts()
    
    user_data = accounts.get(user_id_str, {})
    if not isinstance(user_data, dict) or not user_data.get("accounts"):
        await update.message.reply_text(
            "❌ No accounts found!\n\n"
            "Please contact admin to add accounts for you.\n"
            "Admin: @Notfound_errorx"
        )
        return
    
    user_accounts = user_data["accounts"]
    selected_id = user_data.get("selected_account_id", 1)
    
    message = "📱 Your Accounts 📱\n\n"
    message += "Select an account to use:\n\n"
    
    keyboard = []
    for acc in user_accounts:
        status = "✅" if acc.get('active', True) else "❌"
        login_status = "🔓" if acc.get('token') else "🔒"
        selected_mark = " 👑" if acc['id'] == selected_id else ""
        
        message += f"{status}{login_status} {acc['custom_name']}\n"
        message += f"   └─ 👤 Username: {acc['username']}\n"
        message += f"   └─ 🆔 ID: {acc.get('api_user_id', 'N/A')[:8]}...{selected_mark}\n\n"
        
        callback_data = f"select_account_{acc['id']}"
        keyboard.append([InlineKeyboardButton(
            f"{acc['custom_name']}{selected_mark}", 
            callback_data=callback_data
        )])
    
    keyboard.append([InlineKeyboardButton("🔄 Refresh All", callback_data="refresh_all_accounts")])
    keyboard.append([InlineKeyboardButton("❌ Close", callback_data="close_accounts_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='none')

async def handle_account_selection(update: Update, context: CallbackContext):
    """Handle account selection from menu"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    user_id_str = str(user_id)
    
    if data == "close_accounts_menu":
        await query.delete_message()
        return
    
    if data == "refresh_all_accounts":
        await query.edit_message_text("🔄 Refreshing all accounts...")
        await refresh_user_accounts(user_id)
        
        accounts = load_accounts()
        user_data = accounts.get(user_id_str, {})
        user_accounts = user_data.get("accounts", [])
        selected_id = user_data.get("selected_account_id", 1)
        
        message = "✅ Accounts Refreshed ✅\n\n"
        message += "Updated accounts:\n\n"
        
        for acc in user_accounts:
            status = "✅" if acc.get('active', True) else "❌"
            login_status = "🔓" if acc.get('token') else "🔒"
            selected_mark = " 👑" if acc['id'] == selected_id else ""
            
            message += f"{status}{login_status} {acc['custom_name']}\n"
            message += f"   └─ 👤 Username: {acc['username']}{selected_mark}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("📱 Select Account", callback_data="back_to_accounts")],
            [InlineKeyboardButton("❌ Close", callback_data="close_accounts_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='none')
        return
    
    if data == "back_to_accounts":
        await show_accounts_menu_from_callback(query, context)
        return
    
    if data.startswith("select_account_"):
        account_id = int(data.split("_")[2])
        
        accounts = load_accounts()
        user_data = accounts.get(user_id_str, {})
        if not isinstance(user_data, dict):
            await query.edit_message_text("❌ No accounts found!")
            return
        
        # Find the account
        selected_account = None
        for acc in user_data.get("accounts", []):
            if acc["id"] == account_id:
                selected_account = acc
                break
        
        if not selected_account:
            await query.edit_message_text("❌ Account not found!")
            return
        
        # Try to login to selected account
        await query.edit_message_text(f"🔄 Logging into {selected_account['custom_name']}...")
        
        token, api_user_id, nickname = await login_api_async(
            selected_account['username'], 
            selected_account['password']
        )
        
        if token:
            # Update account info
            for acc in user_data["accounts"]:
                if acc["id"] == account_id:
                    acc['token'] = token
                    acc['api_user_id'] = api_user_id
                    acc['nickname'] = nickname
                    acc['last_login'] = datetime.now().isoformat()
                    acc['active'] = True
                    break
            
            # Set as selected
            user_data["selected_account_id"] = account_id
            user_data["last_active"] = datetime.now().isoformat()
            accounts[user_id_str] = user_data
            save_accounts(accounts)
            
            # Update AccountManager
            await account_manager.initialize_user(user_id)
            
            message = f"✅ Account Switched Successfully! ✅\n\n"
            message += f"📱 Active Account: {selected_account['custom_name']}\n"
            message += f"👤 Username: {selected_account['username']}\n"
            message += f"🆔 API ID: {api_user_id or 'N/A'}\n"
            message += f"👑 Default: {'Yes' if selected_account.get('default', False) else 'No'}\n\n"
            message += f"🔄 Remaining Checks: {account_manager.get_user_remaining_checks(user_id)}\n"
            message += f"✅ Active Login: {account_manager.get_user_active_accounts_count(user_id)}\n\n"
            message += "You can now start checking numbers!"
            
            keyboard = [
                [InlineKeyboardButton("📱 Switch Account", callback_data="back_to_accounts")],
                [InlineKeyboardButton("🚀 Start Checking", callback_data="start_checking")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='none')
        else:
            await query.edit_message_text(
                f"❌ Failed to login to {selected_account['custom_name']}!\n\n"
                f"Please check credentials or contact admin."
            )

async def show_accounts_menu_from_callback(query, context):
    """Show accounts menu from callback"""
    user_id = query.from_user.id
    user_id_str = str(user_id)
    
    accounts = load_accounts()
    
    user_data = accounts.get(user_id_str, {})
    if not isinstance(user_data, dict) or not user_data.get("accounts"):
        await query.edit_message_text(
            "❌ No accounts found!\n\n"
            "Please contact admin to add accounts for you.\n"
            "Admin: @Notfound_errorx"
        )
        return
    
    user_accounts = user_data["accounts"]
    selected_id = user_data.get("selected_account_id", 1)
    
    message = "📱 Your Accounts 📱\n\n"
    message += "Select an account to use:\n\n"
    
    keyboard = []
    for acc in user_accounts:
        status = "✅" if acc.get('active', True) else "❌"
        login_status = "🔓" if acc.get('token') else "🔒"
        selected_mark = " 👑" if acc['id'] == selected_id else ""
        
        message += f"{status}{login_status} {acc['custom_name']}\n"
        message += f"   └─ 👤 Username: {acc['username']}\n"
        message += f"   └─ 🆔 ID: {acc.get('api_user_id', 'N/A')[:8]}...{selected_mark}\n\n"
        
        callback_data = f"select_account_{acc['id']}"
        keyboard.append([InlineKeyboardButton(
            f"{acc['custom_name']}{selected_mark}", 
            callback_data=callback_data
        )])
    
    keyboard.append([InlineKeyboardButton("🔄 Refresh All", callback_data="refresh_all_accounts")])
    keyboard.append([InlineKeyboardButton("❌ Close", callback_data="close_accounts_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='none')

async def refresh_user_accounts(user_id):
    """Refresh all accounts for a user"""
    user_id_str = str(user_id)
    accounts = load_accounts()
    
    user_data = accounts.get(user_id_str, {})
    if not isinstance(user_data, dict):
        return False
    
    updated_count = 0
    for acc in user_data.get("accounts", []):
        if acc.get('active', True):
            token, api_user_id, nickname = await login_api_async(
                acc['username'], 
                acc['password']
            )
            if token:
                acc['token'] = token
                acc['api_user_id'] = api_user_id
                acc['nickname'] = nickname
                acc['last_login'] = datetime.now().isoformat()
                updated_count += 1
    
    user_data["last_active"] = datetime.now().isoformat()
    accounts[user_id_str] = user_data
    save_accounts(accounts)
    
    # Update AccountManager
    await account_manager.initialize_user(user_id)
    
    return updated_count

async def admin_add_account_custom(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
        
    if not context.args or len(context.args) < 4:
        await update.message.reply_text(
            "❌ Usage: `/addacc user_id custom_name username password`\n\n"
            "Example: `/addacc 7319925086 \"Main Account\" RakibulBN pass123`\n"
            "Example: `/addacc 7319925086 \"Backup Account\" RakibulBN2 pass456`\n\n"
            "Note: Use quotes for custom names with spaces"
        )
        return
        
    try:
        target_user_id = context.args[0]
        custom_name = context.args[1]
        username = context.args[2]
        password = context.args[3]
        
        processing_msg = await update.message.reply_text(f"🔄 Verifying account `{username}`...")
        token, api_user_id, nickname = await login_api_async(username, password)
        
        if not token:
            await processing_msg.edit_text(f"❌ Login failed for `{username}`! Please check credentials.")
            return
            
        accounts = load_accounts()
        user_id_str = str(target_user_id)
        
        # Initialize user structure if not exists
        if user_id_str not in accounts:
            accounts[user_id_str] = {
                "accounts": [],
                "selected_account_id": 1,
                "telegram_username": "",
                "last_active": datetime.now().isoformat()
            }
        
        user_data = accounts[user_id_str]
        if not isinstance(user_data, dict):
            user_data = {
                "accounts": [],
                "selected_account_id": 1,
                "telegram_username": "",
                "last_active": datetime.now().isoformat()
            }
        
        # Generate new account ID
        existing_ids = [acc['id'] for acc in user_data.get("accounts", [])]
        new_id = max(existing_ids) + 1 if existing_ids else 1
        
        # Check if account already exists
        account_exists = False
        for acc in user_data.get("accounts", []):
            if acc['username'] == username:
                # Update existing account
                acc['custom_name'] = custom_name
                acc['password'] = password
                acc['token'] = token
                acc['api_user_id'] = api_user_id
                acc['nickname'] = nickname
                acc['last_login'] = datetime.now().isoformat()
                acc['active'] = True
                account_exists = True
                break
        
        if not account_exists:
            # Add new account
            new_account = {
                'id': new_id,
                'custom_name': custom_name,
                'username': username,
                'password': password,
                'token': token,
                'api_user_id': api_user_id,
                'nickname': nickname,
                'last_login': datetime.now().isoformat(),
                'active': True,
                'default': (new_id == 1),  # First account is default
                'added_by': update.effective_user.id,
                'added_at': datetime.now().isoformat(),
                'telegram_username': "",
                'friends': []  # Add friends field
            }
            user_data["accounts"].append(new_account)
        
        # Set as selected if it's the first account
        if new_id == 1:
            user_data["selected_account_id"] = 1
        
        accounts[user_id_str] = user_data
        save_accounts(accounts)
        
        # Update AccountManager
        if user_id_str in account_manager.user_tokens:
            await account_manager.initialize_user(int(target_user_id))
        
        await processing_msg.edit_text(
            f"✅ Account Added Successfully! ✅\n\n"
            f"👤 User ID: `{target_user_id}`\n"
            f"📛 Custom Name: `{custom_name}`\n"
            f"👤 Username: `{username}`\n"
            f"🔑 Password: `{password}`\n"
            f"🆔 API User ID: `{api_user_id or 'N/A'}`\n"
            f"🎯 Account ID: `{new_id}`\n"
            f"👑 Default: `{'Yes' if new_id == 1 else 'No'}`\n"
            f"✅ Auto-login: Successful"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def refresh_server(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    processing_msg = await update.message.reply_text("🔄 Refreshing your accounts...")
    
    active_accounts = await account_manager.initialize_user(user_id)
    
    remaining = account_manager.get_user_remaining_checks(user_id)
    total_accounts = account_manager.get_user_accounts_count(user_id)
    
    if active_accounts == 0:
        await processing_msg.edit_text(
            f"❌ No accounts could be logged in!\n\n"
            f"Please contact admin to check your account credentials.\n"
            f"Admin: @Notfound_errorx"
        )
        return
    
    await processing_msg.edit_text(
        f"✅ Accounts Refreshed Successfully!\n\n"
        f"📊 Result:\n"
        f"• Successfully Logged In: {active_accounts}\n"
        f"• Failed: {total_accounts - active_accounts}"
    )

async def async_add_number_optimized(token, phone, msg, username, serial_number=None, user_id=None, cc='1'):
    """
    Add number with specific country code - IMPROVED VERSION
    Shows actual phone number from API response
    """
    try:
        async with aiohttp.ClientSession() as session:
            added = await add_number_async(session, token, cc, phone)
            prefix = f"{serial_number}. " if serial_number else ""
            
            # Get actual status to see what API says
            status_code, status_name, record_id, actual_phone = await get_status_with_actual_phone(session, token, phone)
            
            if added:
                # Tracking update
                tracking = load_tracking()
                user_id_str = str(user_id)
                
                if user_id_str not in tracking["today_added"]:
                    tracking["today_added"][user_id_str] = 0
                
                tracking["today_added"][user_id_str] += 1
                save_tracking(tracking)
                
                stats = load_stats()
                stats["total_checked"] = stats.get("total_checked", 0) + 1
                stats["today_checked"] = stats.get("today_checked", 0) + 1
                save_stats(stats)
                
                print(f"✅ Added count increased for user {user_id_str} - Number: {phone} (CC: {cc})")
                
                # Show actual phone from API if different
                if actual_phone and actual_phone != phone:
                    display_phone = f"{actual_phone}"
                else:
                    display_phone = phone
                
                await msg.edit_text(f"{prefix}+{cc} {display_phone} 🔵 In Progress")
            else:
                status_code, status_name, record_id, actual_phone = await get_status_with_actual_phone(session, token, phone)
                
                # Show actual phone from API
                if actual_phone and actual_phone != phone:
                    display_phone = f"{actual_phone}"
                    status_name = f"{status_name} - Wrong Format"
                else:
                    display_phone = phone
                
                if status_code == 16:
                    await msg.edit_text(f"{prefix}+{cc} {display_phone} 🚫 Already Exists")
                    account_manager.release_token(token)
                    return
                
                await msg.edit_text(f"{prefix}+{cc} {display_phone} ❌ Add Failed")
                account_manager.release_token(token)
    except Exception as e:
        print(f"❌ Add error for {phone} (CC:{cc}): {e}")
        prefix = f"{serial_number}. " if serial_number else ""
        await msg.edit_text(f"{prefix}+{cc} {phone} ❌ Add Failed")
        account_manager.release_token(token)

async def get_status_with_actual_phone(session, token, phone):
    """
    Get status with actual phone number from API response
    Returns: (status_code, status_name, record_id, actual_phone)
    """
    try:
        headers = {"Admin-Token": token}
        status_url = f"{BASE_URL}/z-number-base/getAullNum?page=1&pageSize=15&phoneNum={phone}"
        
        async with session.get(status_url, headers=headers, timeout=10) as response:
            response_text = await response.text()
            
            if response.status == 401:
                print(f"❌ Token expired for {phone}")
                return -1, "❌ Token Expired", None, phone
            
            try:
                res = await response.json(content_type=None)
            except Exception as json_error:
                print(f"❌ JSON parse attempt 1 failed for {phone}: {json_error}")
                try:
                    cleaned_text = response_text.strip()
                    if cleaned_text.startswith('\ufeff'):
                        cleaned_text = cleaned_text[1:]
                    res = json.loads(cleaned_text)
                except Exception as e2:
                    print(f"❌ Manual JSON parse also failed for {phone}: {e2}")
                    print(f"❌ Raw response: {response_text[:500]}")
                    return -2, "❌ API Error", None, phone
            
            # Check for specific error messages
            if res.get('code') == 28004:
                print(f"❌ Login required for {phone}")
                return -1, "❌ Token Expired", None, phone
            
            error_msg = res.get('msg', '').lower()
            if any(keyword in error_msg for keyword in ["already exists", "cannot register", "number exists", "invalid", "wrong format"]):
                print(f"❌ Number {phone} has issue: {error_msg}")
                return 16, f"🚫 {res.get('msg', 'Already Exists')}", None, phone
            
            if res.get('code') in (400, 409):
                error_msg = res.get('msg', f'Error {res.get("code")}')
                print(f"❌ Number {phone} has issue, code {res.get('code')}: {error_msg}")
                return 16, f"🚫 {error_msg}", None, phone
            
            if (res and "data" in res and "records" in res["data"] and 
                res["data"]["records"] and len(res["data"]["records"]) > 0):
                record = res["data"]["records"][0]
                status_code = record.get("registrationStatus")
                record_id = record.get("id")
                
                # Get actual phone number from API
                actual_phone = record.get("phoneNum")
                if not actual_phone:
                    # Try to extract from other fields
                    phone_fields = ["phone", "phoneNumber", "mobile", "number"]
                    for field in phone_fields:
                        if field in record:
                            actual_phone = record[field]
                            break
                
                status_name = status_map.get(status_code, f"🔸 Status {status_code}")
                return status_code, status_name, record_id, actual_phone or phone
            
            # If no records but successful response
            if res and "data" in res:
                return None, "🚫 Already register or wrong number", None, phone
            
            return None, "🚫 API Response Error", None, phone
            
    except Exception as e:
        print(f"❌ Status error for {phone}: {type(e).__name__}: {e}")
        return -2, "🔄 Refresh Server", None, phone

async def track_status_optimized(context: CallbackContext):
    data = context.job.data
    phone = data['phone']
    token = data['token']
    username = data['username']
    user_id = data['user_id']
    checks = data['checks']
    last_status = data.get('last_status', '🔵 Processing...')
    serial_number = data.get('serial_number')
    last_status_code = data.get('last_status_code')
    cc = data.get('cc', '1')  # Add country code
    
    try:
        async with aiohttp.ClientSession() as session:
            status_code, status_name, record_id, actual_phone = await get_status_with_actual_phone(session, token, phone)
        
        prefix = f"{serial_number}. " if serial_number else ""
        
        # Show actual phone if different
        display_phone = actual_phone if actual_phone and actual_phone != phone else phone
        
        if status_code == -1:
            account_manager.release_token(token)
            error_text = f"{prefix}+{cc} {display_phone} ❌ Token Error (Auto-Retry)"
            try:
                await context.bot.edit_message_text(
                    chat_id=data['chat_id'], 
                    message_id=data['message_id'],
                    text=error_text
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    print(f"❌ Message update failed for {phone}: {e}")
            return
        
        # IMPORTANT FIX: Stop tracking immediately for wrong/duplicate numbers
        immediate_stop_codes = []  # Not Register, Ban, Already Exists, API Error
        
        if status_code in immediate_stop_codes:
            account_manager.release_token(token)
            if phone in active_numbers:
                del active_numbers[phone]
                print(f"🛑 Immediate stop for {phone} - Status: {status_name}")
            
            final_text = f"{prefix}+{cc} {display_phone} {status_name}"
            
            # Add extra info for wrong format
            if status_code == 16 and actual_phone != phone:
                final_text += f""
            
            try:
                await context.bot.edit_message_text(
                    chat_id=data['chat_id'], 
                    message_id=data['message_id'],
                    text=final_text
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    print(f"❌ Final message update failed for {phone}: {e}")
            return
        
        if status_code == 2:
            if phone not in active_numbers:
                active_numbers[phone] = {
                    'token': token,
                    'username': username,
                    'message_id': data['message_id'],
                    'user_id': user_id,
                    'chat_id': data['chat_id']
                }
                print(f"✅ Number {phone} added to active_numbers for OTP submission")
                print(f"📱 Active numbers count: {len(active_numbers)}")
            else:
                print(f"ℹ️ Number {phone} already in active_numbers")
        
        if status_code == 1 and last_status_code != 1:
            print(f"🎉 SUCCESS detected for {phone} by user {user_id}")
            
            tracking = load_tracking()
            user_id_str = str(user_id)
            
            if phone in tracking.get("today_success", {}):
                print(f"ℹ️ Number {phone} already had success today, skipping count")
            else:
                print(f"✅ First time SUCCESS today for {phone} by user {user_id_str}")
                
                otp_stats = load_otp_stats()
                otp_stats["total_success"] = otp_stats.get("total_success", 0) + 1
                otp_stats["today_success"] = otp_stats.get("today_success", 0) + 1
                
                if user_id_str not in otp_stats["user_stats"]:
                    otp_stats["user_stats"][user_id_str] = {
                        "total_success": 0,
                        "today_success": 0,
                        "yesterday_success": 0,
                        "username": username,
                        "full_name": ""
                    }
                otp_stats["user_stats"][user_id_str]["total_success"] = otp_stats["user_stats"][user_id_str].get("total_success", 0) + 1
                otp_stats["user_stats"][user_id_str]["today_success"] = otp_stats["user_stats"][user_id_str].get("today_success", 0) + 1
                
                tracking["today_success"][phone] = user_id_str
                
                if "today_success_counts" not in tracking:
                    tracking["today_success_counts"] = {}
                
                if user_id_str not in tracking["today_success_counts"]:
                    tracking["today_success_counts"][user_id_str] = 0
                tracking["today_success_counts"][user_id_str] = tracking["today_success_counts"][user_id_str] + 1
                
                save_otp_stats(otp_stats)
                save_tracking(tracking)
                print(f"✅ Success count updated for user {user_id_str} - Total: {tracking['today_success_counts'][user_id_str]}")
        
        if status_name != last_status:
            new_text = f"{prefix}+{cc} {display_phone} {status_name}"
            
            # Show actual phone if different
            if actual_phone and actual_phone != phone:
                new_text += f""
            
            try:
                await context.bot.edit_message_text(
                    chat_id=data['chat_id'], 
                    message_id=data['message_id'],
                    text=new_text
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    print(f"❌ Message update failed for {phone}: {e}")
        
        final_states = [0, 1, 4, 7, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16, -2]
        if status_code in final_states:
            account_manager.release_token(token)
            if phone in active_numbers:
                del active_numbers[phone]
                print(f"🗑️ Number {phone} removed from active_numbers (final state: {status_code})")
            
            if status_code not in [1, 2]:
                deleted_count = await delete_number_from_all_accounts_optimized(phone, user_id)
            
            final_text = f"{prefix}+{cc} {display_phone} {status_name}"
            
            # Show actual phone if different
            if actual_phone and actual_phone != phone:
                final_text += f""
            
            try:
                await context.bot.edit_message_text(
                    chat_id=data['chat_id'], 
                    message_id=data['message_id'],
                    text=final_text
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    print(f"❌ Final message update failed for {phone}: {e}")
            return
        
        if checks >= 60:  # Reduced from 150 to 100
            account_manager.release_token(token)
            if phone in active_numbers:
                del active_numbers[phone]
                print(f"⏰ Number {phone} removed from active_numbers (timeout)")
            
            if status_code not in [1, 2]:
                deleted_count = await delete_number_from_all_accounts_optimized(phone, user_id)
            
            timeout_text = f"{prefix}+{cc} {display_phone} 🟡 Try Later"
            
            # Show actual phone if different
            if actual_phone and actual_phone != phone:
                timeout_text += f""
            
            try:
                await context.bot.edit_message_text(
                    chat_id=data['chat_id'], 
                    message_id=data['message_id'],
                    text=timeout_text
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    print(f"❌ Timeout message update failed for {phone}: {e}")
            return
        
        if context.job_queue:
            context.job_queue.run_once(
                track_status_optimized, 
                2,  # Start checking after 2 seconds
                data={
                    **data, 
                    'checks': checks + 1, 
                    'last_status': status_name,
                    'last_status_code': status_code,
                    'cc': cc  # Pass country code
                }
            )
        else:
            print("❌ JobQueue not available, cannot schedule status check")
    except Exception as e:
        print(f"❌ Tracking error for {phone}: {e}")
        account_manager.release_token(token)

async def process_multiple_numbers(update: Update, context: CallbackContext, text: str):
    numbers_data = extract_phone_numbers(text)  # Now returns dict with cc and phone
    
    if not numbers_data:
        await update.message.reply_text("❌ কোনো ভ্যালিড নম্বর পাওয়া যায়নি!")
        return
    
    user_id = update.effective_user.id
    
    for index, num_data in enumerate(numbers_data, 1):
        remaining = account_manager.get_user_remaining_checks(user_id)
        if remaining <= 0:
            active_accounts = account_manager.get_user_active_accounts_count(user_id)
            await update.message.reply_text(f"🚀 Refresh Server.. Processing  {active_accounts * MAX_PER_ACCOUNT}")
            break
            
        token_data = account_manager.get_next_available_token(user_id)
        if not token_data:
            await update.message.reply_text("❌ No available accounts! Please refresh server first.")
            break
            
        token, username = token_data
        
        # Extract phone and cc
        phone = num_data['phone']
        cc = num_data.get('cc', '1')  # Default to 1 if not found
        
        # Stats update
        stats = load_stats()
        stats["total_checked"] = stats.get("total_checked", 0) + 1
        stats["today_checked"] = stats.get("today_checked", 0) + 1
        save_stats(stats)
        
        msg = await update.message.reply_text(f"{index}. {phone} (CC:{cc}) 🔵 Processing...")
        asyncio.create_task(async_add_number_optimized(
            token, phone, msg, username, index, user_id, cc
        ))
        
        if context.job_queue:
            context.job_queue.run_once(
                track_status_optimized, 
                2,
                data={
                    'chat_id': update.message.chat_id,
                    'message_id': msg.message_id,
                    'phone': phone,
                    'token': token,
                    'username': username,
                    'checks': 0,
                    'last_status': '🔵 Processing...',
                    'serial_number': index,
                    'user_id': user_id,
                    'last_status_code': None
                }
            )
            
async def handle_message_optimized(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    # Check if user has accounts
    if account_manager.get_user_accounts_count(user_id) == 0 and user_id != ADMIN_ID:
        await update.message.reply_text(
            f"❌ No accounts assigned to you!\n\n"
            f"Please contact admin to add accounts for you.\n"
            f"Admin: @Notfound_errorx"
        )
        return
    
    text = update.message.text.strip()
    
    # Handle OTP submission if replying to a message
    if update.message.reply_to_message:
        await handle_otp_submission(update, context)
        return
    
    # Handle button clicks
    if text == "🚀 Refresh Server":
        await refresh_server(update, context)
        return
    if text == "📦 My Settlements":
        await show_user_settlements(update, context)
        return
    if text == "📊 Statistics":
        await statistics_command(update, context)
        return
    if text == "📱 Switch Account":
        await show_accounts_menu(update, context)
        return
        
    # Admin menu options
    if user_id == ADMIN_ID:
        if text == "➕ Add Account":
            await update.message.reply_text("👤 Usage: `/addacc user_id custom_name username password`")
            return
        if text == "📋 List Accounts":
            await admin_list_accounts(update, context)
            return
        if text == "💰 Set Rate":
            await update.message.reply_text("💰 Usage: `/setrate amount [date] [country...]`\n📢 Notice: `/setrate notice Your message`")
            return
        if text == "📊 Statistics":
            await statistics_command(update, context)
            return
    
    # Extract phone numbers from text
    numbers_data = extract_phone_numbers(text)  # Returns list of dicts with 'cc' and 'phone'
    
    if numbers_data:
        # IMPORTANT: Take only the first valid number if multiple extracted
        if len(numbers_data) > 1:
            # Filter to get the most likely correct number
            valid_numbers = []
            for num_data in numbers_data:
                phone = num_data['phone']
                cc = num_data.get('cc', '1')
                
                # Check if this looks like a valid number
                # Benin numbers should be 8 digits
                if cc == '229' and len(phone) == 8:
                    valid_numbers.append(num_data)
                elif 7 <= len(phone) <= 15:
                    valid_numbers.append(num_data)
            
            if valid_numbers:
                # Take the first valid one
                num_data = valid_numbers[0]
                await update.message.reply_text(
                    f"ℹ️ Found {len(numbers_data)} possible numbers.\n"
                    f"✅ Processing: +{num_data['cc']} {num_data['phone']}"
                )
            else:
                num_data = numbers_data[0]  # Fallback to first one
        else:
            num_data = numbers_data[0]
        
        phone = num_data['phone']
        cc = num_data.get('cc', '1')  # Default to US/Canada if not found
        
        # Check remaining checks
        remaining = account_manager.get_user_remaining_checks(user_id)
        if remaining <= 0:
            active_accounts = account_manager.get_user_active_accounts_count(user_id)
            await update.message.reply_text(f"🚀 Refresh Server..Processing {active_accounts * MAX_PER_ACCOUNT}")
            return
        
        # Get available token
        token_data = account_manager.get_next_available_token(user_id)
        if not token_data:
            await update.message.reply_text("❌ No available accounts! Please refresh server first.")
            return
        
        token, username = token_data
        
        # Update stats
        stats = load_stats()
        stats["total_checked"] = stats.get("total_checked", 0) + 1
        stats["today_checked"] = stats.get("today_checked", 0) + 1
        save_stats(stats)
        
        # Send processing message
        msg = await update.message.reply_text(f"+{cc} {phone} 🔵 Processing...")
        
        # Start async task to add number
        asyncio.create_task(async_add_number_optimized(
            token, phone, msg, username, user_id=user_id, cc=cc
        ))
        
        # Schedule status tracking
        if context.job_queue:
            context.job_queue.run_once(
                track_status_optimized, 
                2,  # Start checking after 2 seconds
                data={
                    'chat_id': update.message.chat_id,
                    'message_id': msg.message_id,
                    'phone': phone,
                    'token': token,
                    'username': username,
                    'checks': 0,
                    'last_status': '🔵 Processing...',
                    'user_id': user_id,
                    'last_status_code': None,
                    'cc': cc 
                }
            )
        
        return
    
    # If no phone numbers found
    await update.message.reply_text("❌ No valid phone numbers found!\n\n"
                                   "📱 Supported Formats:\n"
                                   "• +1 (234) 567-8900\n"
                                   "• +44 7911 123456\n"
                                   "• +229 47879817\n"
                                   "• (229) 47879817\n"
                                   "• 22947879817\n\n"
                                   "💡 Tip: Include country code with + sign!")

def run_fastapi():
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=RENDER_PORT,
        access_log=False
    )

def main():
    print(f"🚀 Starting Bot on Render (Port: {RENDER_PORT})...")

    # 🔹 FastAPI keep-alive
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    print(f"🌐 FastAPI server started on port {RENDER_PORT}")

    # 🔹 Async loop setup
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def initialize_bot():
        await account_manager.initialize_user(ADMIN_ID)

        asyncio.create_task(keep_alive_enhanced())
        asyncio.create_task(random_ping())
        asyncio.create_task(immediate_ping())

        print("🤖 Bot initialized successfully with enhanced keep-alive!")

    loop.run_until_complete(initialize_bot())

    # 🔹 Telegram Application
    application = Application.builder().token(BOT_TOKEN).build()

    # ───────────────── COMMAND HANDLERS ─────────────────

    application.add_handler(CommandHandler("start", start))

    # ✅ Account system (UPDATED & CLEAN)
    application.add_handler(CommandHandler("addacc", admin_add_account_custom))
    application.add_handler(CommandHandler("removeacc", admin_remove_account))
    application.add_handler(CommandHandler("accounts", show_accounts_menu))

    # 🔹 Admin / System
    application.add_handler(CommandHandler("refresh", refresh_server))
    application.add_handler(CommandHandler("setrate", set_settlement_rate))
    application.add_handler(CommandHandler("settlements", show_user_settlements))

    # 🔹 Statistics
    application.add_handler(CommandHandler("stats", statistics_command))
    application.add_handler(CommandHandler("statistics", statistics_command))

    # ───────────────── CALLBACK HANDLERS ─────────────────

    # Statistics callbacks
    application.add_handler(
        CallbackQueryHandler(handle_statistics_callback, pattern=r"^stats_")
    )

    # Settlement callbacks
    application.add_handler(
        CallbackQueryHandler(handle_settlement_callback, pattern=r"^settlement_")
    )

    # Account menu callbacks
    application.add_handler(
        CallbackQueryHandler(
            handle_account_selection,
            pattern=r"^(select_account_|refresh_all_accounts|close_accounts_menu|back_to_accounts|start_checking)"
        )
    )

    # ───────────────── MESSAGE HANDLER ─────────────────

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_optimized)
    )

    # ───────────────── JOB QUEUE ─────────────────

    if application.job_queue:
        application.job_queue.run_daily(
            reset_daily_stats,
            time=datetime.strptime("10:00", "%H:%M").time()
        )
    else:
        print("❌ JobQueue not available, daily stats reset not scheduled")

    # ───────────────── START BOT ─────────────────

    print("🚀 Bot starting polling with 24/7 keep-alive...")

    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except Exception as e:
        print(f"❌ Bot error: {e}")
        time.sleep(10)
        main()

if __name__ == "__main__":
    main()
