import sys
import os
import re
import base64
import requests
import uuid
import ddddocr
from io import BytesIO

# Configuration
BASE_URL = "https://tathya.uidai.gov.in"
CAPTCHA_URL = f"{BASE_URL}/audioCaptchaService/api/captcha/v3/generation"
OTP_URL = f"{BASE_URL}/unifiedAppAuthService/api/v2/generate/aadhaar/otp"
DOWNLOAD_URL = f"{BASE_URL}/downloadAadhaarService/api/aadhaar/download"

def run_download(eid, chat_id):
    # Session to keep cookies/session state
    session = requests.Session()
    from requests.adapters import HTTPAdapter
    from urllib3.util import Retry
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    
    request_id = str(uuid.uuid4())

    # Browser-like strict headers
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en_IN",
        "Content-Type": "application/json",
        "appid": "MYAADHAAR",
        "x-request-id": request_id,
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
    
    max_captcha_retries = 5
    cap_txn_id = None
    captcha_val = None
    otp_txn_id = None
    last_server_msg = "Failed to send OTP after maximum retries. Please verify details and try again."
    attempt = 1
    captcha_attempts = 0
    max_captcha_attempts = 15
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
            
            # Request OTP
            otp_payload = {
                "eidNumber": eid,
                "idType": "eid",
                "captchaTxnId": cap_txn_id,
                "captchaValue": captcha_val,
                "resendOTP": False,
                "transactionId": request_id
            }

            res_otp = session.post(OTP_URL, json=otp_payload, headers=headers, timeout=45)
            try:
                otp_data = res_otp.json()
            except ValueError:
                raise Exception("Aadhaar Portal returned an invalid non-JSON page during OTP request. Gateway might be down.")

            if otp_data.get('status') == "Success":
                print("✅ OTP Sent Successfully!")
                otp_txn_id = otp_data['txnId']
                break
            else:
                msg = otp_data.get('message') or (otp_data.get('responseData') or {}).get('message') or 'OTP generation failed'
                print(f"Server Response Attempt {attempt}: {msg} | Full JSON: {otp_data}")
                if msg:
                    last_server_msg = msg
                if msg and "technical difficulties" in msg.lower():
                    raise Exception(f"⚠️ UIDAI portal is temporarily facing technical difficulties with this number. Please try again after 1 hour or try with another number. ||| Real Server Response: {msg}")
                # Captcha issue, loop continues to retry
                attempt += 1
        except Exception as ex:
            if attempt == max_captcha_retries or captcha_attempts == max_captcha_attempts:
                raise Exception(f"Failed to solve captcha / send OTP after retries: {ex}")

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

    download_payload = {
        "eid": eid,
        "mask": False,
        "otp": otp_code,
        "otpTxnId": otp_txn_id
    }

    # Add transactionId in headers specifically for the download endpoint
    download_headers = headers.copy()
    download_headers["transactionId"] = request_id

    print("Downloading Aadhaar PDF from UIDAI secure server...")
    res_dl = session.post(DOWNLOAD_URL, json=download_payload, headers=download_headers, timeout=60)
    dl_data = res_dl.json()

    if dl_data.get('status') == "Success":
        pdf_b64 = dl_data['data']['aadhaarPdf']
        
        # Decode base64 PDF
        pdf_bytes = base64.b64decode(pdf_b64)
        
        # Save to cracked_aadhar folder
        script_dir = os.path.dirname(os.path.abspath(__file__))
        cracked_dir = os.path.join(script_dir, "cracked_aadhar")
        os.makedirs(cracked_dir, exist_ok=True)
        file_path = os.path.join(cracked_dir, f"Aadhaar_{chat_id}.pdf")
        
        with open(file_path, "wb") as f:
            f.write(pdf_bytes)
            
        print(f"\n========================================")
        print(f"🎉 SUCCESS! Aadhaar PDF Downloaded Successfully!")
        print(f"📁 Saved as: {file_path}")
        print(f"========================================")
    else:
        error_msg = dl_data.get('statusMessage', 'Download failed. Please check details/OTP.')
        raise Exception(f"Download failed: {error_msg}")

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        EID = sys.argv[1]
        CHAT_ID = sys.argv[2]
    else:
        print("Usage: python aadhar-downlaod.py <EID> <CHAT_ID>")
        sys.exit(1)
        
    try:
        run_download(EID, CHAT_ID)
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)
