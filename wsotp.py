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


BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
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
    """Enhanced keep-alive with multiple strategies for Render"""
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
                            await asyncio.sleep(2)  # Small delay between pings
                except Exception as e:
                    print(f"⚠️ Keep-alive ping failed for {url}: {e}")
            
            # Wait for next ping cycle (3 minutes for Render)
            await asyncio.sleep(3 * 60)
            
        except Exception as e:
            print(f"❌ Keep-alive system error: {e}")
            await asyncio.sleep(3 * 60)

async def random_ping():
    """Additional random pings to avoid pattern detection"""
    while True:
        try:
            random_time = random.randint(2 * 60, 5 * 60)  # 2-5 minutes for Render
            await asyncio.sleep(random_time)
            
            async with aiohttp.ClientSession() as session:
                async with session.get("https://webck-9utn.onrender.com", timeout=10) as response:
                    print(f"🎲 Random ping sent: Status {response.status}")
                    
        except Exception as e:
            print(f"⚠️ Random ping failed: {e}")

async def immediate_ping():
    """Immediate ping on startup"""
    await asyncio.sleep(30)  # Wait 30 seconds after startup
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
            # Ensure proper structure
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
        # Default structure
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
    
    # Get today's date
    today_date = datetime.now().date().isoformat()
    
    # Save today's added stats to yesterday
    tracking["yesterday_added"] = tracking.get("today_added", {}).copy()
    
    # Save today's success stats to daily_stats
    if "daily_stats" not in tracking:
        tracking["daily_stats"] = {}
    
    # Count today's success per user (use today_success_counts)
    today_success_by_user = tracking.get("today_success_counts", {}).copy()
    
    # Save today's success stats
    tracking["daily_stats"][today_date] = today_success_by_user
    
    # Reset today's tracking
    tracking["today_added"] = {}
    tracking["yesterday_success"] = tracking.get("today_success_counts", {}).copy()
    tracking["today_success"] = {}
    tracking["today_success_counts"] = {}
    tracking["last_reset"] = datetime.now().isoformat()
    
    # Also reset global stats
    stats["yesterday_checked"] = stats["today_checked"]
    stats["today_checked"] = 0
    stats["yesterday_deleted"] = stats["today_deleted"]
    stats["today_deleted"] = 0
    
    # Reset OTP stats
    otp_stats["yesterday_success"] = otp_stats["today_success"]
    otp_stats["today_success"] = 0
    
    # Reset user-specific today success
    for user_id_str in otp_stats.get("user_stats", {}):
        otp_stats["user_stats"][user_id_str]["yesterday_success"] = otp_stats["user_stats"][user_id_str].get("today_success", 0)
        otp_stats["user_stats"][user_id_str]["today_success"] = 0
    
    save_stats(stats)
    save_otp_stats(otp_stats)
    save_tracking(tracking)
    print(f"✅ Daily tracking reset (BD Time 4PM) - Date: {today_date}")


# Enhanced file operations with error handling
def load_accounts():
    try:
        # Try multiple possible file locations
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
        # Create initial structure with admin
        initial_data = {
            str(ADMIN_ID): []
        }
        save_accounts(initial_data)
        return initial_data
        
    except Exception as e:
        print(f"❌ Critical error loading accounts: {e}")
        # Create initial structure
        initial_data = {
            str(ADMIN_ID): []
        }
        return initial_data

def save_accounts(accounts):
    try:
        # Try multiple possible file locations
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
                        # Ensure we return a dictionary
                        if isinstance(data, dict):
                            return data
                        else:
                            print(f"⚠️ Stats file contains {type(data)}, returning default")
                            return {
                                "total_checked": 0, 
                                "total_deleted": 0, 
                                "today_checked": 0, 
                                "today_deleted": 0,
                                "yesterday_checked": 0,
                                "yesterday_deleted": 0,
                                "last_reset": datetime.now().isoformat()
                            }
            except:
                continue
        return {
            "total_checked": 0, 
            "total_deleted": 0, 
            "today_checked": 0, 
            "today_deleted": 0,
            "yesterday_checked": 0,
            "yesterday_deleted": 0,
            "last_reset": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"❌ Error loading stats: {e}")
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
        possible_paths = [STATS_FILE, "stats.json", "/tmp/stats.json"]
        for file_path in possible_paths:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(stats, f, indent=4, ensure_ascii=False)
                break
            except:
                continue
    except Exception as e:
        print(f"❌ Error saving stats: {e}")

# OTP Stats file operations
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

# Settings file operations (for settlement rate)
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
        # Default settings
        default_settings = {
            "settlement_rate": 0.10,  # Default rate $0.10
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
                                
                                # Try to decode token to get user ID
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

# Improved phone number extraction - ALL FORMATS
def extract_phone_numbers(text: str) -> List[str]:
    """
    Extract phone numbers from text in various formats:
    - 2269868875
    - 226-243-5292
    - (226) 243-5292
    - +1 (226) 243-5292
    - +12262435292
    - 226.243.5292
    - +15793002372
    - +1 (343) 218-1238
    """
    # First, try to find all phone number patterns
    all_numbers = []
    
    # Pattern 1: +1 (343) 218-1238 or +1(343)218-1238
    pattern1 = r'\+\s*1\s*\(\s*(\d{3})\s*\)\s*(\d{3})\s*[-.\s]*(\d{4})'
    matches1 = re.finditer(pattern1, text, re.IGNORECASE)
    for match in matches1:
        number = match.group(1) + match.group(2) + match.group(3)
        all_numbers.append(number)
    
    # Pattern 2: +15793002372 (11 digits starting with +1)
    pattern2 = r'\+\s*1\s*(\d{10})'
    matches2 = re.finditer(pattern2, text)
    for match in matches2:
        number = match.group(1)
        all_numbers.append(number)
    
    # Pattern 3: (343) 218-1238
    pattern3 = r'\(\s*(\d{3})\s*\)\s*(\d{3})\s*[-.\s]*(\d{4})'
    matches3 = re.finditer(pattern3, text)
    for match in matches3:
        number = match.group(1) + match.group(2) + match.group(3)
        all_numbers.append(number)
    
    # Pattern 4: 343-218-1238 or 343.218.1238 or 343 218 1238
    pattern4 = r'\b(\d{3})\s*[-.\s]\s*(\d{3})\s*[-.\s]\s*(\d{4})\b'
    matches4 = re.finditer(pattern4, text)
    for match in matches4:
        number = match.group(1) + match.group(2) + match.group(3)
        all_numbers.append(number)
    
    # Pattern 5: 10 consecutive digits
    pattern5 = r'\b(\d{10})\b'
    matches5 = re.finditer(pattern5, text)
    for match in matches5:
        number = match.group(1)
        all_numbers.append(number)
    
    # Pattern 6: International format without parentheses
    pattern6 = r'\+\s*1\s*(\d{3})\s*(\d{3})\s*(\d{4})'
    matches6 = re.finditer(pattern6, text)
    for match in matches6:
        number = match.group(1) + match.group(2) + match.group(3)
        all_numbers.append(number)
    
    # Remove any non-digit characters and ensure 10 digits
    cleaned_numbers = []
    for num in all_numbers:
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', num)
        
        # If 11 digits and starts with 1, remove the 1
        if len(digits) == 11 and digits.startswith('1'):
            digits = digits[1:]
        
        # If we have exactly 10 digits, add it
        if len(digits) == 10:
            cleaned_numbers.append(digits)
    
    # Remove duplicates while preserving order
    unique_numbers = []
    seen = set()
    for num in cleaned_numbers:
        if num not in seen:
            unique_numbers.append(num)
            seen.add(num)
    
    # Debug: Print extracted numbers
    print(f"🔍 Text: {text}")
    print(f"📱 Extracted numbers: {unique_numbers}")
    
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

# Status checking - FIXED VERSION
async def get_status_async(session, token, phone):
    try:
        headers = {"Admin-Token": token}
        status_url = f"{BASE_URL}/z-number-base/getAullNum?page=1&pageSize=15&phoneNum={phone}"
        
        async with session.get(status_url, headers=headers, timeout=10) as response:
            response_text = await response.text()
            
            if response.status == 401:
                print(f"❌ Token expired for {phone}")
                return -1, "❌ Token Expired", None
            
            # Try to parse JSON with any content type
            try:
                res = await response.json(content_type=None)
            except Exception as json_error:
                print(f"❌ JSON parse attempt 1 failed for {phone}: {json_error}")
                # Try manual JSON parsing
                try:
                    # Clean the response text
                    cleaned_text = response_text.strip()
                    # Remove any BOM or extra characters
                    if cleaned_text.startswith('\ufeff'):
                        cleaned_text = cleaned_text[1:]
                    
                    # Try to parse as JSON
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
            
            # If no records found but response is successful
            if res and "data" in res and "records" in res["data"]:
                return None, "🚫 Already Registered...", None
            
            return None, "🚫 Already Registered...", None
            
    except Exception as e:
        print(f"❌ Status error for {phone}: {type(e).__name__}: {e}")
        return -2, "🔄 Refresh Server", None

# Async delete
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

# OTP submission function
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
                    # Try to get text response
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

# Settlement functions - FIXED VERSION
async def get_user_settlements(session, token, user_id, page=1, page_size=2):
    """Get settlement records for a specific user - CORRECTED VERSION"""
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
                        
                        # Check if data has the expected structure
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

async def get_all_billing_list(session, token, page=1, page_size=15):
    """Get billing list for admin"""
    try:
        headers = {"Admin-Token": token}
        url = f"{BASE_URL}/z-billinglist/getBillingList?page={page}&pageSize={page_size}"
        
        async with session.get(url, headers=headers, timeout=10) as response:
            if response.status == 200:
                try:
                    result = await response.json(content_type=None)
                    if result.get('code') == 200:
                        return result.get('data', {}), None
                    else:
                        return None, result.get('msg', 'Unknown error')
                except Exception as e:
                    return None, f"JSON parse error: {e}"
            else:
                return None, f"HTTP Error: {response.status}"
    except Exception as e:
        return None, str(e)

# Account Manager
class AccountManager:
    def __init__(self):
        print("🔄 Initializing Account Manager...")
        self.accounts = load_accounts()
        print(f"📊 Loaded accounts for {len(self.accounts)} users")
        
        # User-specific token management
        self.user_tokens = {}  # user_id -> list of tokens
        self.token_owners = {}  # token -> (user_id, username)
        self.token_info = {}  # token -> {'username': '', 'api_user_id': '', 'usage': 0}
        
    async def initialize_user(self, user_id):
        """Initialize accounts for a specific user"""
        user_id_str = str(user_id)
        if user_id_str not in self.accounts:
            print(f"ℹ️ No accounts found for user {user_id}")
            return 0
            
        user_accounts = self.accounts[user_id_str]
        valid_tokens = []
        
        print(f"🔄 Initializing {len(user_accounts)} accounts for user {user_id}")
        
        for acc in user_accounts:
            if not acc.get('active', True):
                print(f"⏭️ Skipping inactive account: {acc['username']}")
                continue
                
            username = acc['username']
            password = acc['password']
            
            if acc.get('token') and acc.get('api_user_id'):
                print(f"🔍 Validating existing token for {username}")
                # Validate existing token
                is_valid = await self.validate_token(acc['token'])
                if is_valid:
                    print(f"✅ Token valid for {username}")
                    valid_tokens.append((username, acc['token'], acc['api_user_id']))
                else:
                    print(f"🔄 Token invalid, re-logging in for {username}")
                    # Try to login again
                    new_token, api_user_id, nickname = await login_api_async(username, password)
                    if new_token:
                        acc['token'] = new_token
                        acc['api_user_id'] = api_user_id
                        acc['nickname'] = nickname
                        acc['last_login'] = datetime.now().isoformat()
                        valid_tokens.append((username, new_token, api_user_id))
                        print(f"✅ Re-login successful for {username}")
                    else:
                        print(f"❌ Re-login failed for {username}")
            else:
                print(f"🔄 First time login for {username}")
                # First time login
                new_token, api_user_id, nickname = await login_api_async(username, password)
                if new_token:
                    acc['token'] = new_token
                    acc['api_user_id'] = api_user_id
                    acc['nickname'] = nickname
                    acc['last_login'] = datetime.now().isoformat()
                    valid_tokens.append((username, new_token, api_user_id))
                    print(f"✅ First login successful for {username}")
                else:
                    print(f"❌ First login failed for {username}")
        
        # Save updated tokens
        save_accounts(self.accounts)
        
        # Store tokens for this user
        self.user_tokens[user_id_str] = []
        for username, token, api_user_id in valid_tokens:
            self.user_tokens[user_id_str].append(token)
            self.token_owners[token] = (user_id_str, username)
            self.token_info[token] = {
                'username': username,
                'api_user_id': api_user_id,
                'usage': 0
            }
        
        print(f"✅ Initialized {len(valid_tokens)} accounts for user {user_id}")
        return len(valid_tokens)
    
    async def validate_token(self, token):
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
        user_id_str = str(user_id)
        if user_id_str in self.accounts:
            active_accounts = [acc for acc in self.accounts[user_id_str] if acc.get('active', True)]
            return len(active_accounts)
        return 0
    
    def get_user_active_accounts_count(self, user_id):
        user_id_str = str(user_id)
        if user_id_str in self.user_tokens:
            return len(self.user_tokens[user_id_str])
        return 0
    
    def get_user_remaining_checks(self, user_id):
        user_id_str = str(user_id)
        if user_id_str not in self.user_tokens:
            return 0
        
        total_slots = len(self.user_tokens[user_id_str]) * MAX_PER_ACCOUNT
        used_slots = sum(self.token_info.get(token, {}).get('usage', 0) for token in self.user_tokens[user_id_str])
        remaining = max(0, total_slots - used_slots)
        return remaining
    
    def get_next_available_token(self, user_id):
        user_id_str = str(user_id)
        if user_id_str not in self.user_tokens or not self.user_tokens[user_id_str]:
            print(f"❌ No valid tokens available for user {user_id}")
            return None
        
        available_tokens = []
        for token in self.user_tokens[user_id_str]:
            info = self.token_info.get(token, {})
            usage = info.get('usage', 0)
            if usage < MAX_PER_ACCOUNT:
                available_tokens.append((token, usage))
        
        if not available_tokens:
            print(f"❌ All accounts are at maximum usage for user {user_id}")
            return None
        
        # Select token with minimum usage
        best_token, best_usage = min(available_tokens, key=lambda x: x[1])
        self.token_info[best_token]['usage'] += 1
        
        username = self.token_info[best_token].get('username', 'Unknown')
        print(f"✅ Using token from {username}, usage: {self.token_info[best_token]['usage']}/{MAX_PER_ACCOUNT}")
        
        return best_token, username
    
    def release_token(self, token):
        if token in self.token_info:
            self.token_info[token]['usage'] = max(0, self.token_info[token]['usage'] - 1)
            username = self.token_info[token].get('username', 'Unknown')
            print(f"✅ Released token from {username}, usage: {self.token_info[token]['usage']}/{MAX_PER_ACCOUNT}")
    
    def get_all_users_stats(self):
        stats = {}
        for user_id_str, accounts in self.accounts.items():
            active_accounts = len([acc for acc in accounts if acc.get('active', True)])
            logged_in_accounts = len(self.user_tokens.get(user_id_str, []))
            stats[user_id_str] = {
                'total_accounts': len(accounts),
                'active_accounts': active_accounts,
                'logged_in_accounts': logged_in_accounts,
                'username': accounts[0]['username'] if accounts else 'Unknown'
            }
        return stats
    
    def get_api_user_id_for_token(self, token):
        """Get API user ID for a specific token"""
        info = self.token_info.get(token, {})
        return info.get('api_user_id')

# Global account manager
account_manager = AccountManager()

# Track active numbers for OTP submission
active_numbers = {}

# Track number status history to detect status changes
number_status_history = {}

# Handle OTP submission - FIXED: Count only when status changes to 1
async def handle_otp_submission(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Check if this is a reply to a number message
    if update.message.reply_to_message:
        replied_message = update.message.reply_to_message.text
        # Extract phone number from replied message
        phone_match = re.search(r'(\d{10})', replied_message)
        if phone_match:
            phone = phone_match.group(1)
            
            # Check if this number is active and belongs to the user
            if phone in active_numbers and active_numbers[phone]['user_id'] == user_id:
                # Check if OTP code is valid (4-6 digits)
                if re.match(r'^\d{4,6}$', text):
                    otp_data = active_numbers[phone]
                    token = otp_data['token']
                    username = otp_data['username']
                    message_id = otp_data['message_id']
                    
                    # Submit OTP
                    processing_msg = await update.message.reply_text(f"🔄 Submitting OTP for {phone}...")
                    
                    async with aiohttp.ClientSession() as session:
                        success, message = await submit_otp_async(session, token, phone, text)
                    
                    if success:
                        # ✅ OTP submit successful, but don't count success yet
                        # Wait for status to change to 1 in track_status_optimized
                        await processing_msg.delete()
                        
                        # Check current status
                        async with aiohttp.ClientSession() as session:
                            status_code, status_name, record_id = await get_status_async(session, token, phone)
                        
                        if status_code is not None:
                            await context.bot.edit_message_text(
                                chat_id=update.effective_chat.id,
                                message_id=message_id,
                                text=f"{phone} {status_name}"
                            )
                    else:
                        await processing_msg.edit_text(f"❌ OTP submission failed for {phone}: {message}")
                else:
                    await update.message.reply_text("❌ Invalid OTP format. Please send 4-6 digit OTP code.")
            else:
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
    
    try:
        async with aiohttp.ClientSession() as session:
            status_code, status_name, record_id = await get_status_async(session, token, phone)
        
        prefix = f"{serial_number}. " if serial_number else ""
        
        if status_code == -1:
            account_manager.release_token(token)
            error_text = f"{prefix}{phone} ❌ Token Error (Auto-Retry)"
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
        
        # Store active number for OTP submission if status is 2 (In Progress)
        if status_code == 2:  # In Progress
            active_numbers[phone] = {
                'token': token,
                'username': username,
                'message_id': data['message_id'],
                'user_id': user_id
            }
        
        # ✅ IMPORTANT: Check if status changed from non-1 to 1 (Success)
        if status_code == 1 and last_status_code != 1:
            # Load tracking data
            tracking = load_tracking()
            user_id_str = str(user_id)
            
            # Check if this number already had success TODAY (DUPLICATE CHECK)
            if phone in tracking.get("today_success", {}):
                # Already had success today - just log, NO COUNT
                print(f"ℹ️ Number {phone} already had success today, skipping count")
            else:
                # First time success today for this number
                print(f"🎉 First time SUCCESS today for {phone} by user {user_id_str}")
                
                # Update OTP stats
                otp_stats = load_otp_stats()
                otp_stats["total_success"] += 1
                otp_stats["today_success"] += 1
                
                # Update user stats
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
                
                # ✅ SIMPLE TRACKING: phone -> user_id mapping
                tracking["today_success"][phone] = user_id_str
                
                # ✅ Also track counts per user
                if "today_success_counts" not in tracking:
                    tracking["today_success_counts"] = {}
                
                if user_id_str not in tracking["today_success_counts"]:
                    tracking["today_success_counts"][user_id_str] = 0
                tracking["today_success_counts"][user_id_str] += 1
                
                save_otp_stats(otp_stats)
                save_tracking(tracking)
                print(f"✅ Success count updated for user {user_id_str} - Number: {phone}")
        
        if status_name != last_status:
            new_text = f"{prefix}{phone} {status_name}"
            try:
                await context.bot.edit_message_text(
                    chat_id=data['chat_id'], 
                    message_id=data['message_id'],
                    text=new_text
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    print(f"❌ Message update failed for {phone}: {e}")
        
        final_states = [0, 1, 4, 7, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16]
        if status_code in final_states:
            account_manager.release_token(token)
            # Remove from active numbers if exists
            if phone in active_numbers:
                del active_numbers[phone]
            
            # ✅ শুধুমাত্র স্ট্যাটাস 1 এবং 2 ছাড়া বাকি সব স্ট্যাটাসে ডিলিট হবে
            if status_code not in [1, 2]:
                deleted_count = await delete_number_from_all_accounts_optimized(phone, user_id)
            
            final_text = f"{prefix}{phone} {status_name}"
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
        
        if checks >= 150:
            account_manager.release_token(token)
            # Remove from active numbers if exists
            if phone in active_numbers:
                del active_numbers[phone]
            
            # ✅ এখানেও স্ট্যাটাস 1 এবং 2 এর জন্য ডিলিট বন্ধ করুন
            if status_code not in [1, 2]:
                deleted_count = await delete_number_from_all_accounts_optimized(phone, user_id)
            
            timeout_text = f"{prefix}{phone} 🟡 Try leter "
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
                1,
                data={
                    **data, 
                    'checks': checks + 1, 
                    'last_status': status_name,
                    'last_status_code': status_code
                }
            )
        else:
            print("❌ JobQueue not available, cannot schedule status check")
    except Exception as e:
        print(f"❌ Tracking error for {phone}: {e}")
        account_manager.release_token(token)

# Delete number from all accounts of a specific user
async def delete_number_from_all_accounts_optimized(phone, user_id):
    accounts = load_accounts()
    user_id_str = str(user_id)
    deleted_count = 0
    
    if user_id_str not in accounts:
        return 0
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for account in accounts[user_id_str]:
            if account.get("token"):
                tasks.append(delete_if_exists(session, account["token"], phone, account['username']))
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if result is True:
                    deleted_count += 1
        stats = load_stats()
        stats["total_deleted"] += deleted_count
        stats["today_deleted"] += deleted_count
        save_stats(stats)
        print(f"✅ Deleted {phone} from {deleted_count} accounts of user {user_id}")
        return deleted_count

async def delete_if_exists(session, token, phone, username):
    try:
        status_code, _, record_id = await get_status_async(session, token, phone)
        if record_id:
            return await delete_single_number_async(session, token, record_id, username)
        return True
    except Exception as e:
        print(f"❌ Delete check error for {phone} in {username}: {e}")
        return False


# Settlement functions for users - FIXED WITH INLINE BUTTONS
async def show_user_settlements(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    
    # Get user's first account token
    if user_id_str not in account_manager.user_tokens or not account_manager.user_tokens[user_id_str]:
        await update.message.reply_text("❌ No active accounts found!")
        return
    
    token = account_manager.user_tokens[user_id_str][0]
    
    # Get API user ID from token
    api_user_id = account_manager.get_api_user_id_for_token(token)
    
    if not api_user_id:
        await update.message.reply_text(
            "❌ Could not find your API user ID.\n\n"
            "Please refresh your accounts by clicking '🚀 Refresh Server' button first."
        )
        return
    
    # Get page number from command args
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
    
    # Calculate totals
    total_count = 0
    total_amount = 0
    for record in records:
        count = record.get('count', 0)
        record_rate = record.get('receiptPrice', 0.10)
        total_count += count
        total_amount += count * record_rate
    
    message = f"📦 **Your Settlement Records**\n\n"
    message += f"📊 **Total Records:** {total_records}\n"
    message += f"🔢 **Total Count:** {total_count}\n"
    message += f"📄 **Page:** {page}/{total_pages}\n\n"
    
    for i, record in enumerate(records, 1):
        record_id = record.get('id', 'N/A')
        if record_id != 'N/A' and len(str(record_id)) > 8:
            record_id = str(record_id)[:8] + '...'
        
        count = record.get('count', 0)
        record_rate = record.get('receiptPrice', 0.10)
        amount = count * record_rate
        gmt_create = record.get('gmtCreate', 'N/A')
        country = record.get('countryName', 'N/A') or record.get('country', 'N/A')
        
        # Format date
        try:
            if gmt_create != 'N/A':
                # Handle different date formats
                if 'T' in gmt_create:
                    date_obj = datetime.fromisoformat(gmt_create.replace('Z', '+00:00'))
                else:
                    date_obj = datetime.strptime(gmt_create, '%Y-%m-%d %H:%M:%S')
                formatted_date = date_obj.strftime('%d %B %Y, %H:%M')
            else:
                formatted_date = 'N/A'
        except:
            formatted_date = gmt_create
        
        message += f"**{i}. Settlement #{record_id}**\n"
        message += f"📅 **Date:** {formatted_date}\n"
        message += f"🌍 **Country:** {country}\n"
        message += f"🔢 **Count:** {count}\n\n"
        
    
    # Add pagination buttons
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
    
    # Add refresh button
    keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data=f"settlement_refresh_{page}")])
    
    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)
        await processing_msg.edit_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await processing_msg.edit_text(message, parse_mode='Markdown')

# Settlement functions for admin
async def show_admin_billing_list(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
    
    # Get admin's first account token
    user_id_str = str(ADMIN_ID)
    if user_id_str not in account_manager.user_tokens or not account_manager.user_tokens[user_id_str]:
        await update.message.reply_text("❌ No active accounts found!")
        return
    
    token = account_manager.user_tokens[user_id_str][0]
    
    # Get page number from command args
    page = 1
    if context.args:
        try:
            page = int(context.args[0])
            if page < 1:
                page = 1
        except:
            pass
    
    processing_msg = await update.message.reply_text("🔄 Loading billing list...")
    
    async with aiohttp.ClientSession() as session:
        data, error = await get_all_billing_list(session, token, page=page, page_size=15)
    
    if error:
        await processing_msg.edit_text(f"❌ Error loading billing list: {error}")
        return
    
    if not data or not data.get('page', {}).get('records'):
        await processing_msg.edit_text("❌ No billing records found!")
        return
    
    page_data = data.get('page', {})
    records = page_data.get('records', [])
    total_records = page_data.get('total', 0)
    total_pages = page_data.get('pages', 1)
    total_se = data.get('totalSe', 0)
    
    message = f"📦 **Admin Billing List** 👑\n\n"
    message += f"📊 **Total Records:** {total_records}\n"
    message += f"📄 **Page:** {page}/{total_pages}\n"
    message += f"💰 **Total SE:** {total_se}\n\n"
    
    for record in records:
        record_id = record.get('id', 'N/A')[:10] + '...' if len(record.get('id', '')) > 10 else record.get('id', 'N/A')
        user_name = record.get('userName', 'N/A')
        agent_name = record.get('agentName', 'N/A')
        country = record.get('countryName', 'N/A')
        count = record.get('count', 0)
        receipt_price = record.get('receiptPrice', 0)
        total_price = count * receipt_price
        gmt_create = record.get('gmtCreate', 'N/A')
        last_settlement = record.get('totalLastSettlement', 'N/A')
        
        # Format date
        try:
            if gmt_create != 'N/A':
                date_obj = datetime.strptime(gmt_create, '%Y-%m-%d %H:%M:%S')
                formatted_date = date_obj.strftime('%d %B %Y • %H:%M')
            else:
                formatted_date = 'N/A'
        except:
            formatted_date = gmt_create
        
        message += f"📦 **Settlement #{record_id}**\n"
        message += f"👤 **User:** {user_name}\n"
        message += f"🤝 **Agent:** {agent_name}\n"
        message += f"🌍 **Country:** {country}\n"
        message += f"📅 **Date:** {formatted_date}\n"
        message += f"🔢 **Count:** {count}\n"
        message += f"💵 **Rate:** ${receipt_price:.2f}\n"
        message += f"💰 **Total:** ${total_price:.2f}\n"
        message += f"🏁 **Last Settlement:** {last_settlement}\n\n"
    
    # Add pagination buttons if needed
    keyboard = []
    if page > 1:
        keyboard.append([InlineKeyboardButton("⬅️ Previous", callback_data=f"billing_{page-1}")])
    if page < total_pages:
        if not keyboard:
            keyboard.append([])
        keyboard[0].append(InlineKeyboardButton("Next ➡️", callback_data=f"billing_{page+1}"))
    
    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)
        await processing_msg.edit_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await processing_msg.edit_text(message, parse_mode='Markdown')
                                       
async def set_settlement_rate(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
        
    if not context.args:
        await update.message.reply_text(
            "✨ **Set Settlement Rate** ✨\n\n"
            "📝 **Usage:** `/setrate amount [date] [country...]`\n"
            "📢 **Notice:** `/setrate notice Your message here`\n\n"
            "📌 **Examples:**\n"
            "• `/setrate 0.08` (Today, all countries)\n"
            "• `/setrate 0.08 2/12` (2nd Dec, all countries)\n"
            "• `/setrate 0.08 Canada` (Today, Canada only)\n"
            "• `/setrate 0.08 Canada Nigeria` (Today, Canada & Nigeria)\n"
            "• `/setrate 0.08 2/12 Canada` (2nd Dec, Canada only)\n"
            "• `/setrate notice Payment will be sent tomorrow` (Send notice)\n\n"
            "💡 **Note:** Date format: DD/MM or YYYY-MM-DD"
        )
        return
        
    try:
        # Check if this is a notice command
        if context.args[0].lower() == 'notice':
            notice_message = ' '.join(context.args[1:])
            if not notice_message:
                await update.message.reply_text("❌ Please provide a notice message!")
                return
            
            accounts = load_accounts()
            sent_count = 0
            
            processing_msg = await update.message.reply_text(f"📢 Sending notice to all users...")
            
            for user_id_str in accounts.keys():
                if user_id_str == str(ADMIN_ID):
                    continue
                
                try:
                    await context.bot.send_message(
                        int(user_id_str),
                        f"📢 **Admin Notice** 📢\n\n"
                        f"{notice_message}\n\n"
                        f"📅 Date: {datetime.now().strftime('%d %B %Y')}"
                    )
                    sent_count += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"❌ Could not send notice to user {user_id_str}: {e}")
            
            await processing_msg.edit_text(
                f"✅ **Notice Sent Successfully!**\n\n"
                f"📢 **Message:** {notice_message}\n"
                f"👥 **Sent to:** {sent_count} users\n"
                f"⏰ **Time:** {datetime.now().strftime('%H:%M:%S')}"
            )
            return
        
        # Parse rate (first argument)
        new_rate = float(context.args[0])
        if new_rate <= 0:
            await update.message.reply_text("❌ Rate must be greater than 0!")
            return
        
        # Initialize variables
        target_date = datetime.now().date()
        date_provided = False
        countries = []
        
        # Parse remaining arguments
        remaining_args = context.args[1:]
        
        # Check for date in arguments
        if remaining_args:
            # Try to parse first argument as date
            first_arg = remaining_args[0]
            date_str = None
            
            # Check if first argument looks like a date
            if '/' in first_arg or '-' in first_arg:
                date_str = first_arg
                remaining_args = remaining_args[1:]  # Remove date from list
            
            if date_str:
                date_provided = True
                try:
                    if '/' in date_str:
                        # Format: 2/12 or 02/12
                        parts = date_str.split('/')
                        if len(parts) == 2:
                            day, month = parts
                            if len(day) == 1:
                                day = '0' + day
                            if len(month) == 1:
                                month = '0' + month
                            current_year = datetime.now().year
                            target_date = datetime.strptime(f"{day}/{month}/{current_year}", "%d/%m/%Y").date()
                        else:
                            await update.message.reply_text("❌ Invalid date format! Use: 2/12 or 02/12")
                            return
                    elif '-' in date_str:
                        # Format: 2023-12-02 or 12-02
                        if len(date_str) == 5:  # 12-02 format
                            month, day = date_str.split('-')
                            current_year = datetime.now().year
                            target_date = datetime.strptime(f"{current_year}-{month}-{day}", "%Y-%m-%d").date()
                        else:
                            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ Date parsing error: {e}\n"
                        "Use format: 2/12 or 2023-12-02"
                    )
                    return
        
        # Remaining arguments are countries
        countries = [country.title() for country in remaining_args]
        
        settings = load_settings()
        old_rate = settings.get('settlement_rate', 0.10)
        
        target_date_str = target_date.strftime('%Y-%m-%d')
        target_date_display = target_date.strftime('%d %B %Y')
        
        # Prepare filter message
        filter_message = ""
        if countries:
            if len(countries) == 1:
                filter_message = f"🌍 **Country Filter:** {countries[0]} only"
            else:
                filter_message = f"🌍 **Countries:** {', '.join(countries)}"
        else:
            filter_message = "🌍 **All Countries**"
        
        # Beautiful processing message
        processing_msg = await update.message.reply_text(
            f"🔄 **Processing Settlement Rate Update**\n\n"
            f"📅 **Date:** {target_date_display}\n"
            f"💰 **New Rate:** ${new_rate:.2f}\n"
            f"{filter_message}\n"
            f"⏳ **Status:** Initializing users..."
        )
        
        accounts = load_accounts()
        all_users_summary = []
        total_users = 0
        total_usd = 0
        total_bdt = 0
        USD_TO_BDT = 125
        
        # Counters
        users_processed = 0
        users_token_refreshed = 0
        users_with_settlements = 0
        users_failed = 0
        
        for user_id_str, user_accounts in accounts.items():
            if user_id_str == str(ADMIN_ID):
                continue
            
            if not user_accounts:
                continue
            
            users_processed += 1
            username = user_accounts[0].get('username', 'Unknown')
            
            # Update progress every 5 users
            if users_processed % 5 == 0:
                try:
                    await processing_msg.edit_text(
                        f"🔄 **Processing Settlement Rate Update**\n\n"
                        f"📅 **Date:** {target_date_display}\n"
                        f"💰 **New Rate:** ${new_rate:.2f}\n"
                        f"{filter_message}\n"
                        f"⏳ **Status:** Processing {users_processed} users...\n"
                        f"✅ **Found:** {users_with_settlements} users with settlements"
                    )
                except:
                    pass
            
            # STEP 1: Get or refresh user token
            user_token = None
            token_refreshed = False
            
            if user_id_str in account_manager.user_tokens and account_manager.user_tokens[user_id_str]:
                user_token = account_manager.user_tokens[user_id_str][0]
                
                # Validate token
                async with aiohttp.ClientSession() as session:
                    status_code, _, _ = await get_status_async(session, user_token, "0000000000")
                
                if status_code == -1:
                    user_token = None
            
            # If no valid token, try to login
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
            
            # Save updated accounts
            save_accounts(accounts)
            
            # Get API user ID
            api_user_id = None
            for acc in user_accounts:
                if acc.get('token') == user_token:
                    api_user_id = acc.get('api_user_id')
                    break
            
            if not api_user_id:
                users_failed += 1
                continue
            
            # STEP 2: Fetch settlements with country filter
            try:
                async with aiohttp.ClientSession() as session:
                    settlement_data, error = await get_user_settlements(session, user_token, str(api_user_id), page=1, page_size=100)
                
                if error or not settlement_data or not settlement_data.get('records'):
                    continue
                
                # Filter settlements
                filtered_settlements = []
                for record in settlement_data.get('records', []):
                    gmt_create = record.get('gmtCreate')
                    if not gmt_create:
                        continue
                    
                    try:
                        # Parse date
                        if 'T' in gmt_create:
                            record_date = datetime.fromisoformat(gmt_create.replace('Z', '+00:00')).date()
                        else:
                            record_date = datetime.strptime(gmt_create, '%Y-%m-%d %H:%M:%S').date()
                        
                        # Check date
                        if record_date != target_date:
                            continue
                        
                        # Get country
                        country = record.get('countryName') or record.get('country') or 'Unknown'
                        
                        # Check country filter
                        if countries and country not in countries:
                            continue
                        
                        filtered_settlements.append({
                            'record': record,
                            'date': record_date,
                            'country': country,
                            'count': record.get('count', 0)
                        })
                        
                    except Exception as e:
                        continue
                
                if not filtered_settlements:
                    continue
                
                users_with_settlements += 1
                
                # Group by country
                country_totals = {}
                for item in filtered_settlements:
                    country = item['country']
                    if country not in country_totals:
                        country_totals[country] = 0
                    country_totals[country] += item['count']
                
                # Calculate totals
                total_count = sum(country_totals.values())
                total_usd_user = total_count * new_rate
                total_bdt_user = total_usd_user * USD_TO_BDT
                
                user_summary = {
                    'user_id': user_id_str,
                    'username': username,
                    'api_user_id': api_user_id,
                    'settlement_date': target_date_display,
                    'countries': list(country_totals.keys()),
                    'country_totals': country_totals,
                    'total_count': total_count,
                    'total_usd': total_usd_user,
                    'total_bdt': total_bdt_user,
                    'num_records': len(filtered_settlements),
                    'token_refreshed': token_refreshed
                }
                
                all_users_summary.append(user_summary)
                total_users += 1
                total_usd += total_usd_user
                total_bdt += total_bdt_user
                
            except Exception as e:
                users_failed += 1
                continue
        
        # Save new rate
        settings['settlement_rate'] = new_rate
        settings['last_updated'] = datetime.now().isoformat()
        settings['updated_by'] = ADMIN_ID
        save_settings(settings)
        
        # STEP 3: Send notifications to users
        notified_users = 0
        for user_summary in all_users_summary:
            try:
                # Prepare message
                message = "✨ **Settlement Rate Update** ✨\n\n"
                message += "📢 **Notification for Your Account**\n\n"
                
                message += "📋 **Details:**\n"
                message += f"• 📅 **Date:** {user_summary['settlement_date']}\n"
                
                if len(user_summary['countries']) == 1:
                    message += f"• 🌍 **Country:** {user_summary['countries'][0]}\n"
                else:
                    message += f"• 🌍 **Countries:** {', '.join(user_summary['countries'])}\n"
                
                # Show country-wise breakdown if multiple countries
                if len(user_summary['country_totals']) > 1:
                    message += "\n📊 **Country Breakdown:**\n"
                    for country, count in user_summary['country_totals'].items():
                        country_usd = count * new_rate
                        message += f"• {country}: {count} counts = ${country_usd:.2f}\n"
                
                message += f"• 🔢 **Total Count:** {user_summary['total_count']}\n\n"
                
                message += "💰 **Payment Calculation:**\n"
                message += f"• 📈 **New Rate:** ${new_rate:.2f}\n"
                message += f"• 💵 **Total USD:** ${user_summary['total_usd']:.2f}\n"
                message += f"• 🇧🇩 **Total BDT:** {user_summary['total_bdt']:.2f} BDT\n\n"
                
                if user_summary['token_refreshed']:
                    message += "🔄 **Note:** Your account was auto-refreshed\n\n"
                
                message += "💳 **Payment Information:**\n"
                message += "Please contact the admin to receive your payment.\n\n"
                message += "📞 **Contact Admin for Payment Collection**"
                
                await context.bot.send_message(
                    int(user_summary['user_id']),
                    message,
                    parse_mode='Markdown'
                )
                notified_users += 1
                await asyncio.sleep(1)
            except Exception as e:
                print(f"❌ Notification failed: {e}")
        
        # STEP 4: Send admin summary in multiple messages
        if all_users_summary:
            # First, send the main summary
            summary_message = "🎯 **Settlement Rate Update Complete** 🎯\n\n"
            
            summary_message += "📊 **Operation Summary:**\n"
            summary_message += f"• 📅 **Target Date:** {target_date_display}\n"
            summary_message += f"• 🔄 **Previous Rate:** ${old_rate:.2f}\n"
            summary_message += f"• ✅ **New Rate:** ${new_rate:.2f}\n"
            summary_message += f"• 💱 **Exchange Rate:** 1 USD = {USD_TO_BDT} BDT\n"
            summary_message += f"• {filter_message}\n\n"
            
            summary_message += "📈 **Processing Statistics:**\n"
            summary_message += f"• 👥 **Total Users:** {users_processed}\n"
            summary_message += f"• 🔄 **Auto-Refreshed:** {users_token_refreshed}\n"
            summary_message += f"• ✅ **With Settlements:** {users_with_settlements}\n"
            summary_message += f"• ❌ **Failed:** {users_failed}\n"
            summary_message += f"• 📨 **Notifications Sent:** {notified_users}\n\n"
            
            summary_message += "💰 **Financial Summary:**\n"
            summary_message += f"• 👥 **Total Users:** {total_users}\n"
            summary_message += f"• 💵 **Total USD:** ${total_usd:.2f}\n"
            summary_message += f"• 🇧🇩 **Total BDT:** {total_bdt:.2f} BDT\n"
            summary_message += f"• 📊 **Total Records:** {sum(u['num_records'] for u in all_users_summary)}\n\n"
            
            summary_message += "✅ **Operation Successful!**\n"
            summary_message += f"All notifications have been sent to {notified_users} users."
            summary_message += f"\n\n⏰ **Completed at:** {datetime.now().strftime('%H:%M:%S')}"
            
            await processing_msg.edit_text(summary_message, parse_mode='Markdown')
            
            # Now send user details in chunks of 10 users per message
            users_per_message = 10
            total_chunks = (len(all_users_summary) + users_per_message - 1) // users_per_message
            
            for chunk_index in range(total_chunks):
                start_idx = chunk_index * users_per_message
                end_idx = min(start_idx + users_per_message, len(all_users_summary))
                chunk = all_users_summary[start_idx:end_idx]
                
                details_message = f"📋 **User Details - Part {chunk_index + 1}/{total_chunks}** 📋\n\n"
                details_message += f"📅 **Date:** {target_date_display}\n"
                details_message += f"💰 **Rate:** ${new_rate:.2f}\n\n"
                
                for i, user_summary in enumerate(chunk, start=start_idx + 1):
                    refresh_icon = " 🔄" if user_summary['token_refreshed'] else ""
                    details_message += f"**{i}. {user_summary['username']}**{refresh_icon}\n"
                    details_message += f"   ├─ 👤 **ID:** {user_summary['api_user_id']}\n"
                    
                    if len(user_summary['countries']) == 1:
                        details_message += f"   ├─ 🌍 **Country:** {user_summary['countries'][0]}\n"
                    else:
                        details_message += f"   ├─ 🌍 **Countries:** {', '.join(user_summary['countries'])}\n"
                    
                    # Show country breakdown for multiple countries
                    if len(user_summary['country_totals']) > 1:
                        for country, count in user_summary['country_totals'].items():
                            details_message += f"   ├─ • {country}: {count}\n"
                    
                    details_message += f"   ├─ 🔢 **Count:** {user_summary['total_count']}\n"
                    details_message += f"   ├─ 💵 **USD:** ${user_summary['total_usd']:.2f}\n"
                    details_message += f"   └─ 🇧🇩 **BDT:** {user_summary['total_bdt']:.2f}\n\n"
                
                # Add chunk summary
                chunk_usd = sum(u['total_usd'] for u in chunk)
                chunk_bdt = sum(u['total_bdt'] for u in chunk)
                details_message += f"📊 **Chunk {chunk_index + 1} Total:**\n"
                details_message += f"• 👥 Users: {len(chunk)}\n"
                details_message += f"• 💵 USD: ${chunk_usd:.2f}\n"
                details_message += f"• 🇧🇩 BDT: {chunk_bdt:.2f}\n\n"
                
                if chunk_index < total_chunks - 1:
                    details_message += "⬇️ **More details in next message...**"
                
                try:
                    await context.bot.send_message(
                        ADMIN_ID,
                        details_message,
                        parse_mode='Markdown'
                    )
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"❌ Error sending chunk {chunk_index + 1}: {e}")
            
            # Send final detailed payment summary
            if countries and len(countries) > 0:
                # Calculate total by country
                country_summary = {}
                for user_summary in all_users_summary:
                    for country, count in user_summary['country_totals'].items():
                        if country not in country_summary:
                            country_summary[country] = 0
                        country_summary[country] += count
                
                if country_summary:
                    country_message = "🌍 **Country-Wise Summary** 🌍\n\n"
                    country_message += f"📅 **Date:** {target_date_display}\n"
                    country_message += f"💰 **Rate:** ${new_rate:.2f}\n\n"
                    
                    for country, count in country_summary.items():
                        country_usd = count * new_rate
                        country_bdt = country_usd * USD_TO_BDT
                        country_message += f"**{country}:**\n"
                        country_message += f"• 🔢 **Count:** {count}\n"
                        country_message += f"• 💵 **USD:** ${country_usd:.2f}\n"
                        country_message += f"• 🇧🇩 **BDT:** {country_bdt:.2f}\n\n"
                    
                    try:
                        await context.bot.send_message(
                            ADMIN_ID,
                            country_message,
                            parse_mode='Markdown'
                        )
                    except:
                        pass
            
            # Send overall payment summary
            payment_message = "💰 **Final Payment Summary** 💰\n\n"
            payment_message += f"📅 **Date:** {target_date_display}\n"
            payment_message += f"💰 **Rate:** ${new_rate:.2f}\n"
            
            if countries:
                payment_message += f"🌍 **Countries:** {', '.join(countries)}\n"
            
            payment_message += f"💱 **1 USD =** {USD_TO_BDT} BDT\n\n"
            
            payment_message += "📊 **Final Totals:**\n"
            payment_message += f"• 👥 **Total Users:** {total_users}\n"
            payment_message += f"• 💵 **Total USD:** ${total_usd:.2f}\n"
            payment_message += f"• 🇧🇩 **Total BDT:** {total_bdt:.2f}\n\n"
            
            payment_message += "💳 **Payment Distribution Complete**\n"
            payment_message += "✅ All users have been notified."
            
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    payment_message,
                    parse_mode='Markdown'
                )
            except:
                pass
            
        else:
            # No settlements found
            summary_message = "🎯 **Settlement Rate Update Complete** 🎯\n\n"
            
            summary_message += "📊 **Operation Summary:**\n"
            summary_message += f"• 📅 **Target Date:** {target_date_display}\n"
            summary_message += f"• 🔄 **Previous Rate:** ${old_rate:.2f}\n"
            summary_message += f"• ✅ **New Rate:** ${new_rate:.2f}\n"
            summary_message += f"• {filter_message}\n\n"
            
            summary_message += "📈 **Processing Statistics:**\n"
            summary_message += f"• 👥 **Total Users:** {users_processed}\n"
            summary_message += f"• 🔄 **Auto-Refreshed:** {users_token_refreshed}\n"
            summary_message += f"• ❌ **Failed:** {users_failed}\n\n"
            
            if countries:
                summary_message += f"📭 **No settlements found for {target_date_display} in {', '.join(countries)}**\n"
            else:
                summary_message += f"📭 **No settlements found for {target_date_display}**\n"
            
            summary_message += f"ℹ️ **Rate Updated:** ${new_rate:.2f} (for future settlements)\n\n"
            summary_message += f"⏰ **Completed at:** {datetime.now().strftime('%H:%M:%S')}"
            
            await processing_msg.edit_text(summary_message, parse_mode='Markdown')
        
    except ValueError:
        await update.message.reply_text(
            "❌ **Invalid Command Format!**\n\n"
            "📝 **Usage:** `/setrate amount [date] [country...]`\n"
            "📢 **Notice:** `/setrate notice Your message`\n\n"
            "✅ **Examples:**\n"
            "• `/setrate 0.08`\n"
            "• `/setrate 0.08 Canada`\n"
            "• `/setrate 0.08 Canada Nigeria`\n"
            "• `/setrate 0.08 2/12 Canada`\n"
            "• `/setrate notice Payment tomorrow`"
        )

# Admin view specific user settlements
async def admin_view_user_settlements(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
        
    if not context.args:
        await update.message.reply_text("❌ Usage: `/viewuser user_id [page]`\nExample: `/viewuser 123456789 1`")
        return
    
    try:
        target_user_id = context.args[0]
        page = 1
        if len(context.args) > 1:
            page = int(context.args[1])
            if page < 1:
                page = 1
    except:
        await update.message.reply_text("❌ Invalid arguments!")
        return
    
    # Get admin's first account token
    user_id_str = str(ADMIN_ID)
    if user_id_str not in account_manager.user_tokens or not account_manager.user_tokens[user_id_str]:
        await update.message.reply_text("❌ No active accounts found!")
        return
    
    token = account_manager.user_tokens[user_id_str][0]
    
    processing_msg = await update.message.reply_text(f"🔄 Loading settlements for user {target_user_id}...")
    
    async with aiohttp.ClientSession() as session:
        data, error = await get_user_settlements(session, token, target_user_id, page=page, page_size=5)
    
    if error:
        await processing_msg.edit_text(f"❌ Error loading settlements: {error}")
        return
    
    if not data or not data.get('records'):
        await processing_msg.edit_text(f"❌ No settlement records found for user {target_user_id}!")
        return
    
    records = data.get('records', [])
    total_records = data.get('total', 0)
    total_pages = data.get('pages', 1)
    
    # Get settlement rate from settings
    settings = load_settings()
    rate = settings.get('settlement_rate', 0.10)
    
    message = f"📦 **Settlements for User:** `{target_user_id}` 👑\n\n"
    message += f"📊 **Total Records:** {total_records}\n"
    message += f"📄 **Page:** {page}/{total_pages}\n"
    message += f"💵 **Current Rate:** ${rate:.2f}\n\n"
    
    for i, record in enumerate(records, 1):
        count = record.get('count', 0)
        total_price = count * rate
        gmt_create = record.get('gmtCreate', 'N/A')
        country = record.get('countryName', 'N/A')
        user_name = record.get('userName', 'N/A')
        agent_name = record.get('agentName', 'N/A')
        
        # Format date
        try:
            if gmt_create != 'N/A':
                date_obj = datetime.strptime(gmt_create, '%Y-%m-%d %H:%M:%S')
                formatted_date = date_obj.strftime('%d %B %Y, %H:%M')
            else:
                formatted_date = 'N/A'
        except:
            formatted_date = gmt_create
        
        message += f"📦 **Record #{i}**\n"
        message += f"👤 **User:** {user_name}\n"
        message += f"🤝 **Agent:** {agent_name}\n"
        message += f"📅 **Date:** {formatted_date}\n"
        message += f"🌍 **Country:** {country}\n"
        message += f"🔢 **Count:** {count}\n"
        message += f"💵 **Rate:** ${rate:.2f}\n"
        message += f"💰 **Total:** ${total_price:.2f}\n\n"
    
    # Add pagination buttons if needed
    keyboard = []
    if page > 1:
        keyboard.append([InlineKeyboardButton("⬅️ Previous", callback_data=f"admin_user_{target_user_id}_{page-1}")])
    if page < total_pages:
        if not keyboard:
            keyboard.append([])
        keyboard[0].append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_user_{target_user_id}_{page+1}"))
    
    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)
        await processing_msg.edit_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await processing_msg.edit_text(message, parse_mode='Markdown')

# Handle settlement callbacks - FIXED VERSION
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
        
        # Get user's first account token
        if user_id_str not in account_manager.user_tokens or not account_manager.user_tokens[user_id_str]:
            await query.edit_message_text("❌ No active accounts found!")
            return
        
        token = account_manager.user_tokens[user_id_str][0]
        
        # Get API user ID from token
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
        
        # Calculate totals
        total_count = 0
        total_amount = 0
        for record in records:
            count = record.get('count', 0)
            record_rate = record.get('receiptPrice', 0.10)
            total_count += count
            total_amount += count * record_rate
        
        message = f"📦 **Your Settlement Records**\n\n"
        message += f"📊 **Total Records:** {total_records}\n"
        message += f"🔢 **Total Count:** {total_count}\n"
        message += f"📄 **Page:** {page}/{total_pages}\n\n"
        
        for i, record in enumerate(records, 1):
            record_id = record.get('id', 'N/A')
            if record_id != 'N/A' and len(str(record_id)) > 8:
                record_id = str(record_id)[:8] + '...'
            
            count = record.get('count', 0)
            record_rate = record.get('receiptPrice', 0.10)
            amount = count * record_rate
            gmt_create = record.get('gmtCreate', 'N/A')
            country = record.get('countryName', 'N/A') or record.get('country', 'N/A')
            
            # Format date
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
            
            message += f"**{i}. Settlement #{record_id}**\n"
            message += f"📅 **Date:** {formatted_date}\n"
            message += f"🌍 **Country:** {country}\n"
            message += f"🔢 **Count:** {count}\n"
            
        
        # Update keyboard
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
        
        # Add refresh button
        keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data=f"settlement_refresh_{page}")])
        
        if keyboard:
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await query.edit_message_text(message, parse_mode='Markdown')
    
    elif data.startswith('billing_'):
        # Admin billing pagination
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("❌ Admin only command!")
            return
        
        page = int(data.split('_')[1])
        
        # Get admin's first account token
        user_id_str = str(ADMIN_ID)
        if user_id_str not in account_manager.user_tokens or not account_manager.user_tokens[user_id_str]:
            await query.edit_message_text("❌ No active accounts found!")
            return
        
        token = account_manager.user_tokens[user_id_str][0]
        
        async with aiohttp.ClientSession() as session:
            data_result, error = await get_all_billing_list(session, token, page=page, page_size=15)
        
        if error:
            await query.edit_message_text(f"❌ Error loading billing list: {error}")
            return
        
        if not data_result or not data_result.get('page', {}).get('records'):
            await query.edit_message_text("❌ No billing records found!")
            return
        
        page_data = data_result.get('page', {})
        records = page_data.get('records', [])
        total_records = page_data.get('total', 0)
        total_pages = page_data.get('pages', 1)
        total_se = data_result.get('totalSe', 0)
        
        message = f"📦 **Admin Billing List** 👑\n\n"
        message += f"📊 **Total Records:** {total_records}\n"
        message += f"📄 **Page:** {page}/{total_pages}\n"
        message += f"💰 **Total SE:** {total_se}\n\n"
        
        for record in records:
            record_id = record.get('id', 'N/A')[:10] + '...' if len(record.get('id', '')) > 10 else record.get('id', 'N/A')
            user_name = record.get('userName', 'N/A')
            agent_name = record.get('agentName', 'N/A')
            country = record.get('countryName', 'N/A')
            count = record.get('count', 0)
            receipt_price = record.get('receiptPrice', 0)
            total_price = count * receipt_price
            gmt_create = record.get('gmtCreate', 'N/A')
            last_settlement = record.get('totalLastSettlement', 'N/A')
            
            # Format date
            try:
                if gmt_create != 'N/A':
                    date_obj = datetime.strptime(gmt_create, '%Y-%m-%d %H:%M:%S')
                    formatted_date = date_obj.strftime('%d %B %Y • %H:%M')
                else:
                    formatted_date = 'N/A'
            except:
                formatted_date = gmt_create
            
            message += f"📦 **Settlement #{record_id}**\n"
            message += f"👤 **User:** {user_name}\n"
            message += f"🤝 **Agent:** {agent_name}\n"
            message += f"🌍 **Country:** {country}\n"
            message += f"📅 **Date:** {formatted_date}\n"
            message += f"🔢 **Count:** {count}\n"
            message += f"💵 **Rate:** ${receipt_price:.2f}\n"
            message += f"💰 **Total:** ${total_price:.2f}\n"
            message += f"🏁 **Last Settlement:** {last_settlement}\n\n"
        
        # Update keyboard
        keyboard = []
        if page > 1:
            keyboard.append([InlineKeyboardButton("⬅️ Previous", callback_data=f"billing_{page-1}")])
        if page < total_pages:
            if not keyboard:
                keyboard.append([])
            keyboard[0].append(InlineKeyboardButton("Next ➡️", callback_data=f"billing_{page+1}"))
        
        if keyboard:
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await query.edit_message_text(message, parse_mode='Markdown')
    
    elif data.startswith('admin_user_'):
        # Admin view specific user pagination
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("❌ Admin only command!")
            return
        
        parts = data.split('_')
        target_user_id = parts[2]
        page = int(parts[3])
        
        # Get admin's first account token
        user_id_str = str(ADMIN_ID)
        if user_id_str not in account_manager.user_tokens or not account_manager.user_tokens[user_id_str]:
            await query.edit_message_text("❌ No active accounts found!")
            return
        
        token = account_manager.user_tokens[user_id_str][0]
        
        async with aiohttp.ClientSession() as session:
            data_result, error = await get_user_settlements(session, token, target_user_id, page=page, page_size=5)
        
        if error:
            await query.edit_message_text(f"❌ Error loading settlements: {error}")
            return
        
        if not data_result or not data_result.get('records'):
            await query.edit_message_text(f"❌ No settlement records found for user {target_user_id}!")
            return
        
        records = data_result.get('records', [])
        total_records = data_result.get('total', 0)
        total_pages = data_result.get('pages', 1)
        
        # Get settlement rate from settings
        settings = load_settings()
        rate = settings.get('settlement_rate', 0.10)
        
        message = f"📦 **Settlements for User:** `{target_user_id}` 👑\n\n"
        message += f"📊 **Total Records:** {total_records}\n"
        message += f"📄 **Page:** {page}/{total_pages}\n"
        message += f"💵 **Current Rate:** ${rate:.2f}\n\n"
        
        for i, record in enumerate(records, 1):
            count = record.get('count', 0)
            total_price = count * rate
            gmt_create = record.get('gmtCreate', 'N/A')
            country = record.get('countryName', 'N/A')
            user_name = record.get('userName', 'N/A')
            agent_name = record.get('agentName', 'N/A')
            
            # Format date
            try:
                if gmt_create != 'N/A':
                    date_obj = datetime.strptime(gmt_create, '%Y-%m-%d %H:%M:%S')
                    formatted_date = date_obj.strftime('%d %B %Y, %H:%M')
                else:
                    formatted_date = 'N/A'
            except:
                formatted_date = gmt_create
            
            message += f"📦 **Record #{i}**\n"
            message += f"👤 **User:** {user_name}\n"
            message += f"🤝 **Agent:** {agent_name}\n"
            message += f"📅 **Date:** {formatted_date}\n"
            message += f"🌍 **Country:** {country}\n"
            message += f"🔢 **Count:** {count}\n"
            message += f"💵 **Rate:** ${rate:.2f}\n"
            message += f"💰 **Total:** ${total_price:.2f}\n\n"
        
        # Update keyboard
        keyboard = []
        if page > 1:
            keyboard.append([InlineKeyboardButton("⬅️ Previous", callback_data=f"admin_user_{target_user_id}_{page-1}")])
        if page < total_pages:
            if not keyboard:
                keyboard.append([])
            keyboard[0].append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_user_{target_user_id}_{page+1}"))
        
        if keyboard:
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await query.edit_message_text(message, parse_mode='Markdown')

# Admin Commands
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
        
        # Try to login first to verify credentials
        processing_msg = await update.message.reply_text(f"🔄 Verifying account `{username}`...")
        token, api_user_id, nickname = await login_api_async(username, password)
        
        if not token:
            await processing_msg.edit_text(f"❌ Login failed for `{username}`! Please check credentials.")
            return
            
        # Add account to database
        accounts = load_accounts()
        user_id_str = str(target_user_id)
        
        if user_id_str not in accounts:
            accounts[user_id_str] = []
        
        # Check if account already exists
        account_exists = False
        for acc in accounts[user_id_str]:
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
            # Add new account
            accounts[user_id_str].append({
                'username': username,
                'password': password,
                'token': token,
                'api_user_id': api_user_id,
                'nickname': nickname,
                'last_login': datetime.now().isoformat(),
                'active': True,
                'added_by': update.effective_user.id,
                'added_at': datetime.now().isoformat()
            })
        
        save_accounts(accounts)
        
        # Initialize account for user if they are currently active
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
        
        if user_id_str not in accounts:
            await update.message.reply_text(f"❌ No accounts found for user `{target_user_id}`")
            return
        
        # Find and remove the account
        removed = False
        new_accounts = []
        for acc in accounts[user_id_str]:
            if acc['username'] == username:
                removed = True
                # Remove token from active tokens if exists
                if acc.get('token') and acc['token'] in account_manager.token_info:
                    del account_manager.token_info[acc['token']]
                if acc.get('token') and acc['token'] in account_manager.token_owners:
                    del account_manager.token_owners[acc['token']]
            else:
                new_accounts.append(acc)
        
        if removed:
            accounts[user_id_str] = new_accounts
            save_accounts(accounts)
            
            # Update user tokens
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
    
    for user_id_str, user_accounts in accounts.items():
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

# FIXED STATISTICS FUNCTIONS
async def show_stats(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name or "User"
    
    stats = load_stats()
    otp_stats = load_otp_stats()
    tracking = load_tracking()
    
    remaining = account_manager.get_user_remaining_checks(user_id)
    active_accounts_count = account_manager.get_user_active_accounts_count(user_id)
    total_slots = active_accounts_count * MAX_PER_ACCOUNT
    used_slots = total_slots - remaining if total_slots > 0 else 0
    
    # Get user-specific stats
    user_id_str = str(user_id)
    
    # User's today added (from tracking)
    user_today_added = tracking.get("today_added", {}).get(user_id_str, 0)
    user_yesterday_added = tracking.get("yesterday_added", {}).get(user_id_str, 0)
    
    # User's today success
    user_today_otp = tracking.get("today_success_counts", {}).get(user_id_str, 0)
    
    # Get yesterday's success stats
    yesterday_date = (datetime.now() - timedelta(days=1)).date().isoformat()
    user_yesterday_otp = 0
    
    if yesterday_date in tracking.get("daily_stats", {}):
        user_yesterday_otp = tracking["daily_stats"][yesterday_date].get(user_id_str, 0)
    
    if user_id == ADMIN_ID:
        message = f"📊 Statistics Dashboard 👑\n\n"
        
        settings = load_settings()
        rate = settings.get('settlement_rate', 0.10)
        
        message += f"💰 Settlement Rate: ${rate:.2f}\n"
        message += f"📱 Your Account Status:\n"
        message += f"• Active Login: {active_accounts_count}\n"
        message += f"• Checks Used: {used_slots}/{total_slots}\n"
        message += f"• Remaining: {remaining}\n\n"
        
        message += f"📈 Today's Added: {user_today_added}\n"
        message += f"📈 Yesterday's Added: {user_yesterday_added}\n\n"
        
        message += f"✅ OTP Success:\n"
        message += f"• Today: {user_today_otp}\n"
        message += f"• Yesterday: {user_yesterday_otp}"
    else:
        message = (
            f"📊 Statistics Dashboard\n\n"
            f"👤 User: {user_name}\n\n"
            f"📱 Account Status:\n"
            f"• Active Login: {active_accounts_count}\n"
            f"• Checks Used: {used_slots}/{total_slots}\n"
            f"• Remaining: {remaining}\n\n"
            f"📈 Today's Added: {user_today_added}\n"
            f"📈 Yesterday's Added: {user_yesterday_added}\n\n"
            f"✅ OTP Success:\n"
            f"• Today: {user_today_otp}\n"
            f"• Yesterday: {user_yesterday_otp}\n\n"
            f"⏰ Last Updated: {datetime.now().strftime('%d %b %Y, %H:%M')}"
        )
    
    await update.message.reply_text(message)

# FIXED ADMIN USER STATS
async def admin_user_stats(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
    
    # Get page number from args
    page = 1
    if context.args:
        try:
            page = int(context.args[0])
            if page < 1:
                page = 1
        except:
            pass
    
    processing_msg = await update.message.reply_text("🔄 Loading user statistics...")
    
    accounts = load_accounts()
    otp_stats = load_otp_stats()
    tracking = load_tracking()
    
    # Remove admin from accounts
    user_accounts = {k: v for k, v in accounts.items() if k != str(ADMIN_ID)}
    
    if not user_accounts:
        await processing_msg.edit_text("❌ No user stats available!")
        return
    
    # Calculate totals from tracking
    total_today_added = sum(tracking.get("today_added", {}).values())
    total_yesterday_added = sum(tracking.get("yesterday_added", {}).values())
    total_today_otp = sum(tracking.get("today_success_counts", {}).values())
    
    # For yesterday, check daily_stats
    yesterday_date = (datetime.now() - timedelta(days=1)).date().isoformat()
    total_yesterday_otp = 0
    if yesterday_date in tracking.get("daily_stats", {}):
        total_yesterday_otp = sum(tracking["daily_stats"][yesterday_date].values())
    
    # Pagination
    users_per_page = 25
    all_user_ids = list(user_accounts.keys())
    
    total_pages = (len(all_user_ids) + users_per_page - 1) // users_per_page
    
    # Get users for current page
    start_idx = (page - 1) * users_per_page
    end_idx = start_idx + users_per_page
    page_user_ids = all_user_ids[start_idx:end_idx]
    
    message = "📊 User Statistics Dashboard 👑\n"
    message += f"📄 Page: {page}/{total_pages}\n\n"
    
    message += f"👥 Total Users: {len(user_accounts)}\n"
    message += f"📊 Total Added (Today): {total_today_added}\n"
    message += f"📊 Total Added (Yesterday): {total_yesterday_added}\n"
    message += f"✅ Total OTP Success (Today): {total_today_otp}\n"
    message += f"✅ Total OTP Success (Yesterday): {total_yesterday_otp}\n\n"
    
    for user_id_str in page_user_ids:
        if user_id_str == str(ADMIN_ID):
            continue
            
        user_info = user_accounts[user_id_str]
        if not user_info:
            continue
        
        # Get username from first account
        username = user_info[0].get('username', 'Unknown') if user_info else 'Unknown'
        
        # Get user stats from tracking
        user_today_added = tracking.get("today_added", {}).get(user_id_str, 0)
        user_yesterday_added = tracking.get("yesterday_added", {}).get(user_id_str, 0)
        user_today_otp = tracking.get("today_success_counts", {}).get(user_id_str, 0)
        
        # Get yesterday's success from daily_stats
        user_yesterday_otp = 0
        if yesterday_date in tracking.get("daily_stats", {}):
            user_yesterday_otp = tracking["daily_stats"][yesterday_date].get(user_id_str, 0)
        
        # Get user OTP info for full name
        user_otp_info = otp_stats.get('user_stats', {}).get(user_id_str, {})
        user_full_name = user_otp_info.get('full_name', '')
        
        # Calculate remaining checks
        remaining = account_manager.get_user_remaining_checks(int(user_id_str))
        logged_in = account_manager.get_user_active_accounts_count(int(user_id_str))
        total_slots = logged_in * MAX_PER_ACCOUNT
        used_slots = total_slots - remaining if total_slots > 0 else 0
        
        # Display user info
        display_name = user_full_name if user_full_name else username
        message += f"👤 User: {display_name}\n"
        message += f"🆔 ID: {user_id_str}\n"
        message += f"📱 Accounts: {len(user_info)} | 🔓 Logged: {logged_in}\n"
        message += f"📈 Today Added: {user_today_added} | Yesterday: {user_yesterday_added}\n"
        message += f"✅ OTP Today: {user_today_otp} | Yesterday: {user_yesterday_otp}\n"
        message += f"────────────────────\n\n"
    
    # Add pagination buttons if needed
    keyboard = []
    row = []
    
    if page > 1:
        row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"userstats_{page-1}"))
    
    if page < total_pages:
        row.append(InlineKeyboardButton("Next ➡️", callback_data=f"userstats_{page+1}"))
    
    if row:
        keyboard.append(row)
        reply_markup = InlineKeyboardMarkup(keyboard)
        await processing_msg.edit_text(message, reply_markup=reply_markup)
    else:
        await processing_msg.edit_text(message)

# Handle userstats pagination callbacks
async def handle_userstats_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    page = int(data.split('_')[1])
    
    # Update the callback query message
    await query.edit_message_text("🔄 Loading user statistics...")
    
    # Now call admin_user_stats with the page number
    context.args = [str(page)]
    await admin_user_stats(update, context)

# Bot command handlers
async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    # 🔴 NEW CODE: Send user info to Telegram group
    try:
        user = update.effective_user
        user_info = f"""
🆕 **New User Started Bot** 🆕

👤 **Full Name:** {user.full_name or 'N/A'}
🆔 **User ID:** `{user.id}`
📛 **Username:** @{user.username if user.username else 'N/A'}
📅 **Date:** {datetime.now().strftime('%d %B %Y, %H:%M:%S')}
        """
        
        # Send to your Telegram group
        await context.bot.send_message(
            chat_id="@userupdate4209",
            text=user_info,
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"⚠️ Failed to send user info to group: {e}")
    # 🔴 NEW CODE END
    
    # Initialize user accounts
    active_accounts = await account_manager.initialize_user(user_id)
    
    if user_id == ADMIN_ID:
        keyboard = [
            [KeyboardButton("➕ Add Account"), KeyboardButton("📋 List Accounts")],
            [KeyboardButton("🚀 Refresh Server"), KeyboardButton("📊 Statistics")],
            [KeyboardButton("📦 Billing List"), KeyboardButton("👤 View User")],
            [KeyboardButton("💰 Set Rate"), KeyboardButton("📊 User Stats")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        remaining = account_manager.get_user_remaining_checks(user_id)
        total_accounts = account_manager.get_user_accounts_count(user_id)
        active_accounts_count = account_manager.get_user_active_accounts_count(user_id)
        
        await update.message.reply_text(
            f"🔥 WA OTP 👑\n\n"
            f"✅ Active Login: {active_accounts_count}\n\n"
            f"💡 OTP Tip: Reply to any 'In Progress' number with OTP code",
            reply_markup=reply_markup
        )
        return
        
    # Regular users
    keyboard = [
        [KeyboardButton("🚀 Refresh Server"), KeyboardButton("📊 Statistics")],
        [KeyboardButton("📦 My Settlements")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    remaining = account_manager.get_user_remaining_checks(user_id)
    total_accounts = account_manager.get_user_accounts_count(user_id)
    active_accounts_count = account_manager.get_user_active_accounts_count(user_id)
    
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
        f"✅ Active Login: {active_accounts_count}\n\n"
        f"💡 OTP Tip: Reply to any 'In Progress' number with OTP code",
        reply_markup=reply_markup
    )

async def refresh_server(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    processing_msg = await update.message.reply_text("🔄 Refreshing your accounts...")
    
    # Re-initialize user accounts
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

async def async_add_number_optimized(token, phone, msg, username, serial_number=None, user_id=None):
    try:
        async with aiohttp.ClientSession() as session:
            # Try to add the number
            added = await add_number_async(session, token, 11, phone)
            prefix = f"{serial_number}. " if serial_number else ""
            
            if added:
                # ✅ শুধু status = 2 (processing) হলে count করবেন
                # First, check the status
                status_code, status_name, record_id = await get_status_async(session, token, phone)
                
                if status_code == 2:  # Only count if status is "In Progress"
                    # ✅ Load tracking and update user-specific added count
                    tracking = load_tracking()
                    user_id_str = str(user_id)
                    
                    if user_id_str not in tracking["today_added"]:
                        tracking["today_added"][user_id_str] = 0
                    
                    tracking["today_added"][user_id_str] += 1
                    save_tracking(tracking)
                    
                    # Also update global stats
                    stats = load_stats()
                    stats["total_checked"] += 1
                    stats["today_checked"] += 1
                    save_stats(stats)
                    
                    print(f"✅ Added count increased for user {user_id_str} - Number: {phone} (Status: {status_code})")
                
                await msg.edit_text(f"{prefix}{phone} 🔵 In Progress")
            else:
                status_code, status_name, record_id = await get_status_async(session, token, phone)
                if status_code == 16:
                    await msg.edit_text(f"{prefix}{phone} 🚫 Already Exists")
                    account_manager.release_token(token)
                    return
                await msg.edit_text(f"{prefix}{phone} ❌ Add Failed")
                account_manager.release_token(token)
    except Exception as e:
        print(f"❌ Add error for {phone}: {e}")
        prefix = f"{serial_number}. " if serial_number else ""
        await msg.edit_text(f"{prefix}{phone} ❌ Add Failed")
        account_manager.release_token(token)

# Process multiple numbers from a single message
async def process_multiple_numbers(update: Update, context: CallbackContext, text: str):
    """Process multiple phone numbers from a single message"""
    numbers = extract_phone_numbers(text)
    
    if not numbers:
        await update.message.reply_text("❌ কোনো ভ্যালিড নম্বর পাওয়া যায়নি!")
        return
    
    user_id = update.effective_user.id
    
    # Start processing immediately without any notification message
    for index, phone in enumerate(numbers, 1):
        remaining = account_manager.get_user_remaining_checks(user_id)
        if remaining <= 0:
            # Only notify if all accounts are full
            active_accounts = account_manager.get_user_active_accounts_count(user_id)
            await update.message.reply_text(f"❌ All accounts full! Max {active_accounts * MAX_PER_ACCOUNT}")
            break
            
        token_data = account_manager.get_next_available_token(user_id)
        if not token_data:
            # Only notify if no accounts available
            await update.message.reply_text("❌ No available accounts! Please refresh server first.")
            break
            
        token, username = token_data
        stats = load_stats()
        stats["total_checked"] += 1
        stats["today_checked"] += 1
        save_stats(stats)
        
        # Only change: add serial number to the message
        msg = await update.message.reply_text(f"{index}. {phone} 🔵 Processing...")
        asyncio.create_task(async_add_number_optimized(token, phone, msg, username, index, user_id))
        
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
    
    # Check if user has any accounts
    if account_manager.get_user_accounts_count(user_id) == 0 and user_id != ADMIN_ID:
        await update.message.reply_text(
            f"❌ No accounts assigned to you!\n\n"
            f"Please contact admin to add accounts for you.\n"
            f"Admin: @Notfound_errorx"
        )
        return
    
    text = update.message.text.strip()
    
    # Check if this is an OTP code first
    if update.message.reply_to_message:
        await handle_otp_submission(update, context)
        return
    
    # Handle menu buttons
    if text == "🚀 Refresh Server":
        await refresh_server(update, context)
        return
    if text == "📊 Statistics":
        await show_stats(update, context)
        return
    if text == "📦 My Settlements":
        await show_user_settlements(update, context)
        return
        
    # Handle admin menu buttons
    if user_id == ADMIN_ID:
        if text == "➕ Add Account":
            await update.message.reply_text("👤 Usage: `/addacc user_id username password`")
            return
        if text == "📋 List Accounts":
            await admin_list_accounts(update, context)
            return
        if text == "👤 View User":
            await update.message.reply_text("👤 Usage: `/viewuser user_id [page]`")
            return
        if text == "📦 Billing List":
            await show_admin_billing_list(update, context)
            return
        if text == "💰 Set Rate":
            await update.message.reply_text("💰 Usage: `/setrate amount`")
            return
        if text == "📊 User Stats":
            await admin_user_stats(update, context)
            return
    
    # Handle phone numbers (single or multiple)
    numbers = extract_phone_numbers(text)
    if numbers:
        if len(numbers) == 1:
            # Single number processing
            phone = numbers[0]
            remaining = account_manager.get_user_remaining_checks(user_id)
            if remaining <= 0:
                active_accounts = account_manager.get_user_active_accounts_count(user_id)
                await update.message.reply_text(f"❌ All accounts full! Max {active_accounts * MAX_PER_ACCOUNT}")
                return
            token_data = account_manager.get_next_available_token(user_id)
            if not token_data:
                await update.message.reply_text("❌ No available accounts! Please refresh server first.")
                return
            token, username = token_data
            stats = load_stats()
            stats["total_checked"] += 1
            stats["today_checked"] += 1
            save_stats(stats)
            msg = await update.message.reply_text(f"{phone} 🔵 Processing...")
            asyncio.create_task(async_add_number_optimized(token, phone, msg, username, user_id=user_id))
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
                        'user_id': user_id,
                        'last_status_code': None
                    }
                )
        else:
            # Multiple numbers processing with serial numbers
            await process_multiple_numbers(update, context, text)
        return
    
    # If no numbers found and not a command
    await update.message.reply_text("❓ নম্বর পাঠান বা মেনু ব্যবহার করুন!")

# Run FastAPI server with Render PORT
def run_fastapi():
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=RENDER_PORT,
        access_log=False
    )

def main():
    print(f"🚀 Starting Bot on Render (Port: {RENDER_PORT})...")
    
    # Start FastAPI server in a separate thread
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    print(f"🌐 FastAPI server started on port {RENDER_PORT}")
    
    # Initialize bot
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def initialize_bot():
        # Initialize admin accounts first
        await account_manager.initialize_user(ADMIN_ID)
        
        # Start enhanced keep-alive system
        asyncio.create_task(keep_alive_enhanced())
        asyncio.create_task(random_ping()) 
        asyncio.create_task(immediate_ping())
        
        print("🤖 Bot initialized successfully with enhanced keep-alive!")
    
    loop.run_until_complete(initialize_bot())
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add all handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addacc", admin_add_account))
    application.add_handler(CommandHandler("removeacc", admin_remove_account))
    application.add_handler(CommandHandler("refresh", refresh_server))
    application.add_handler(CommandHandler("setrate", set_settlement_rate))
    application.add_handler(CommandHandler("viewuser", admin_view_user_settlements))
    application.add_handler(CommandHandler("settlements", show_user_settlements))
    application.add_handler(CommandHandler("billing", show_admin_billing_list))
    application.add_handler(CommandHandler("userstats", admin_user_stats))
    application.add_handler(CallbackQueryHandler(handle_settlement_callback, pattern=r"^(settlement_|billing_|admin_user_)"))
    application.add_handler(CallbackQueryHandler(handle_userstats_callback, pattern=r"^userstats_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_optimized))
    
    if application.job_queue:
        # Reset daily stats at 4PM Bangladesh Time (10:00 UTC)
        application.job_queue.run_daily(reset_daily_stats, time=datetime.strptime("10:00", "%H:%M").time())
    else:
        print("❌ JobQueue not available, daily stats reset not scheduled")
    
    print("🚀 Bot starting polling with 24/7 keep-alive...")
    
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except Exception as e:
        print(f"❌ Bot error: {e}")
        # Auto-restart after 10 seconds
        time.sleep(10)
        main()

if __name__ == "__main__":
    main()
