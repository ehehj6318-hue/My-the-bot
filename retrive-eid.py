import sys
import os
import re
import base64
import requests
import uuid
import ddddocr
import json
from io import BytesIO

# Configuration
BASE_URL = "https://tathya.uidai.gov.in"
CAPTCHA_URL = f"{BASE_URL}/audioCaptchaService/api/captcha/v3/generation"
RETRIEVE_URL = f"{BASE_URL}/retrieveEidUid/ext/v1/generic/retrieveuideid"

def run_retrieval(name, dob, mobile):
    if name == "WAIT_INPUT" or dob == "WAIT_INPUT":
        print("🔑 WAITING_FOR_NAME_DOB")
        sys.stdout.flush()
        line = sys.stdin.readline().strip()
        if not line:
            raise Exception("No input received during pre-warm phase.")
        parts = line.split('|')
        if len(parts) >= 2:
            name = parts[0]
            dob = parts[1]
        else:
            name = parts[0]

    if dob == "None" or dob == "null" or dob == "":
        dob = None

    # Session starts here (to maintain cookies)
    session = requests.Session()
    from requests.adapters import HTTPAdapter
    from urllib3.util import Retry
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    
    request_id = str(uuid.uuid4())

    # Strict Browser-like Headers
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en_IN",
        "Content-Type": "application/json",
        "appID": "MYAADHAAR",
        "X-Request-ID": request_id,
        "Origin": "https://myaadhaar.uidai.gov.in",
        "Referer": "https://myaadhaar.uidai.gov.in/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Connection": "keep-alive"
    }

    print("--- STEP 1: Fetching Captcha ---")
    captcha_payload = {
        "captchaLength": "6", 
        "captchaType": "2", 
        "audioCaptchaRequired": True
    }
    
    # Generate list of name candidates (prefixes) to try sequentially
    candidate_names = []
    name_clean = name.strip()
    
    if name_clean.lower() == "mr":
        candidate_names = ["Mr", "Mr.", "Shri", "Sh.", "Kumar"]
    elif name_clean.lower() == "mrs":
        candidate_names = ["Mrs", "Mrs.", "Ms", "Ms.", "Smt", "Smt.", "Miss", "Kumari"]
    else:
        candidate_names = [name_clean]

    cap_txn_id = None
    otp_txn_id = None
    last_server_msg = "Failed to send OTP. Try changing prefix to 'Mrs. ' or 'Ms. ' in the code."
    
    success_details_payload = None
    success_captcha_val = None
    technical_diff = False
    
    for full_name in candidate_names:
        if technical_diff:
            break
        print(f"🔍 [RETRIEVAL] Trying name payload: '{full_name}'...")
        
        max_captcha_retries = 3
        attempt = 1
        captcha_attempts = 0
        max_captcha_attempts = 10
        candidate_success = False
        
        while attempt <= max_captcha_retries and captcha_attempts < max_captcha_attempts:
            captcha_attempts += 1
            try:
                res_cap = session.post(CAPTCHA_URL, json=captcha_payload, headers=headers, timeout=30)
                res_cap.raise_for_status()
                try:
                    cap_data = res_cap.json()
                except ValueError:
                    raise Exception("Aadhaar Portal returned an invalid non-JSON page during captcha load. Gateway might be down.")
                
                if not cap_data or 'imageBase64' not in cap_data or 'transactionId' not in cap_data:
                    raise Exception("UIDAI captcha generation failed. Invalid server response.")
                
                img_b64 = cap_data['imageBase64']
                cap_txn_id = cap_data['transactionId']

                # Solve captcha with ddddocr
                img_bytes = base64.b64decode(img_b64)
                if attempt >= 3:
                    print(f"🔑 MANUAL CAPTCHA REQUIRED | {img_b64}")
                    sys.stdout.flush()
                    captcha_val = sys.stdin.readline().strip()
                    if not captcha_val:
                        raise Exception("No manual captcha entered.")
                else:
                    ocr = ddddocr.DdddOcr(show_ad=False)
                    res = ocr.classification(img_bytes)
                    captcha_val = str(res or '').strip()
                    captcha_val = re.sub(r'[^a-zA-Z0-9]', '', captcha_val)
                    
                    if len(captcha_val) != 6:
                        print(f"⚠️ [OCR] Rejected noisy read '{captcha_val}' (Length {len(captcha_val)} != 6). Fetching new captcha...")
                        continue
                    
                print(f"Decoded Captcha: {captcha_val}")
                
                details_payload = {
                    "name": full_name,
                    "mobileNumber": str(mobile),
                    "dob": dob,
                    "email": None,
                    "captcha": captcha_val,
                    "captchaTxnId": cap_txn_id,
                    "option": "EID",
                    "otp": None,
                    "otpTxnId": None,
                    "resendOtp": False
                }

                res_otp = session.post(RETRIEVE_URL, json=details_payload, headers=headers, timeout=45)
                try:
                    otp_res_json = res_otp.json()
                except ValueError:
                    raise Exception("Aadhaar Portal returned an invalid non-JSON page during EID search. Gateway might be down.")

                res_data = otp_res_json.get('responseData') or {}
                if otp_res_json.get('status') == "Success" or res_data.get('otpSent'):
                    otp_txn_id = res_data.get('otpTxnId')
                    if otp_txn_id:
                        print(f"✅ OTP Sent Successfully for Name: {full_name}")
                        candidate_success = True
                        success_details_payload = details_payload
                        success_captcha_val = captcha_val
                        break

                # If not broken by success, log the response and check for errors
                msg = res_data.get('message') or otp_res_json.get('message') or ''
                print(f"Server Response for '{full_name}' (Attempt {attempt}): {msg}")
                if msg:
                    last_server_msg = msg

                if msg and "technical difficulties" in msg.lower():
                    technical_diff = True
                    last_server_msg = f"⚠️ UIDAI portal is temporarily facing technical difficulties with this number. Please try again after 1 hour or try with another number. ||| Real Server Response: {msg}"
                    break

                if msg and any(x in msg.lower() for x in ["mismatch", "no record", "validation failed", "invalid"]):
                    print(f"📦 Response for '{full_name}': {msg}. Trying next name payload candidate...")
                    break

                # Captcha issue, loop continues to retry for current candidate
                attempt += 1
            except Exception as ex:
                if attempt == max_captcha_retries or captcha_attempts == max_captcha_attempts:
                    print(f"⚠️ Error for '{full_name}' on attempt {attempt}: {ex}")
                    break
        
        if technical_diff:
            break
        if candidate_success:
            break

    if not otp_txn_id:
        raise Exception(last_server_msg)

    # Prompt for OTP
    print("\n" + "="*60)
    print("🔑 ENTER THE OTP RECEIVED ON YOUR REGISTERED MOBILE")
    sys.stdout.flush()
    otp_code = sys.stdin.readline().strip()
    print("="*60)

    if not otp_code:
        raise Exception("No OTP entered.")

    final_payload = success_details_payload.copy()
    final_payload["otp"] = otp_code
    final_payload["otpTxnId"] = otp_txn_id
    final_payload["captcha"] = success_captcha_val 

    res_final = session.post(RETRIEVE_URL, json=final_payload, headers=headers, timeout=45)
    final_data = res_final.json()

    if final_data.get('status') == "Success":
        res_data = final_data.get('responseData') or {}
        print("\n" + "="*60)
        print("📊 FULL SERVER RESPONSE DATA:")
        print(json.dumps(final_data, indent=4))
        print("="*60)

        captured_id = res_data.get('eidNumber') or res_data.get('uidNumber') or res_data.get('aadhaarNumber')
        captured_name = res_data.get('name')
        if captured_id:
            print(f"\n✅ CAPTURED ID SUCCESSFULLY: {captured_id}")
            if captured_name:
                print(f"👤 CAPTURED NAME SUCCESSFULLY: {captured_name}")
    else:
        error_msg = final_data.get('responseData', {}).get('message', 'Incorrect OTP')
        raise Exception(f"OTP submission failed: {error_msg}")

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        NAME = sys.argv[1]
        DOB = sys.argv[2]
        MOBILE = sys.argv[3]
    else:
        # Prompt user dynamically if no arguments are provided
        print("Please enter Aadhaar Holder Name (with prefix if any):")
        sys.stdout.flush()
        NAME = sys.stdin.readline().strip()
        
        print("Please enter Date of Birth (DD-MM-YYYY):")
        sys.stdout.flush()
        DOB = sys.stdin.readline().strip()
        
        print("Please enter Registered Mobile Number:")
        sys.stdout.flush()
        MOBILE = sys.stdin.readline().strip()

    try:
        run_retrieval(NAME, DOB, MOBILE)
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)
