#!/usr/bin/env python3
"""
Simple standalone test for the Neovolt authentication.

This test doesn't rely on importing the Home Assistant integration.
"""
import sys
import base64
import hashlib
import json
import requests
from Crypto.Cipher import AES

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def encrypt_password(password: str, username: str) -> str:
    """
    Encrypt password using the Neovolt API method.
    
    The encryption uses:
    - Key: SHA-256 hash of username
    - IV: MD5 hash of username
    - AES-CBC mode with PKCS7 padding
    - Base64 encoding of the final encrypted data
    """
    try:
        # 1) Derive key & iv from the username
        key = hashlib.sha256(username.encode('utf-8')).digest()  # 32 bytes
        iv = hashlib.md5(username.encode('utf-8')).digest()  # 16 bytes

        # 2) PKCS#7 pad the password to 16-byte blocks
        data = password.encode('utf-8')
        pad_len = AES.block_size - (len(data) % AES.block_size)
        data += bytes([pad_len]) * pad_len

        # 3) AES-CBC encrypt and Base64-encode
        cipher = AES.new(key, AES.MODE_CBC, iv)
        ct = cipher.encrypt(data)
        return base64.b64encode(ct).decode('ascii')
    
    except Exception as e:
        logging.error(f"Error encrypting password: {str(e)}")
        return ""

def test_encryption():
    """Test the encryption with known test cases."""
    test_cases = [
        {
            "username": "caraa",
            "password": "1",
            "expected": "CH1iL1FqYK9bhTd9izZyMA=="
        },
        {
            "username": "carraa",
            "password": "1",
            "expected": "oFzzKemj3O4WP92FBSjZzw=="
        }
    ]
    
    all_passed = True
    for i, case in enumerate(test_cases):
        username = case["username"]
        password = case["password"]
        expected = case["expected"]
        
        encrypted = encrypt_password(password, username)
        
        if encrypted == expected:
            logging.info(f"Test case {i+1} PASSED")
        else:
            logging.error(f"Test case {i+1} FAILED")
            logging.error(f"  Expected: {expected}")
            logging.error(f"  Got: {encrypted}")
            all_passed = False
    
    return all_passed

def test_api_login(username, password, base_url="https://monitor.byte-watt.com"):
    """Test login to the ByteWatt API."""
    login_url = f"{base_url}/api/usercenter/cloud/user/login"
    
    # First, try with encrypted password using JSON payload
    encrypted_password = encrypt_password(password, username)
    logging.info(f"Encrypted password: {encrypted_password}")
    
    payload = {
        "username": username,
        "password": encrypted_password
    }
    
    try:
        logging.info(f"Attempting login with encrypted password to {login_url}")
        
        response = requests.post(
            login_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        logging.info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("code") == 0 or result.get("code") == 200:
                logging.info("Login successful with encrypted password!")
                
                token = None
                if "token" in result:
                    token = result["token"]
                elif "data" in result and result["data"] and "token" in result["data"]:
                    token = result["data"]["token"]
                
                if token:
                    logging.info(f"Token received: {token[:10]}...")
                    return True
                else:
                    logging.warning("Login succeeded but no token in response")
                    return False
            else:
                logging.warning(f"Login failed with code {result.get('code')}: {result.get('msg')}")
                
                # Try fallback
                return test_api_login_fallback(username, password, base_url)
        else:
            logging.error(f"API request failed with status {response.status_code}")
            if response.status_code < 500:  # Only print response text for non-server errors
                logging.error(f"Response: {response.text}")
            
            # Try fallback
            return test_api_login_fallback(username, password, base_url)
            
    except Exception as e:
        logging.error(f"Error during API request: {str(e)}")
        
        # Try fallback
        return test_api_login_fallback(username, password, base_url)
    
    return False

def test_api_login_fallback(username, password, base_url="https://monitor.byte-watt.com"):
    """Test login with form data as a fallback."""
    login_url = f"{base_url}/api/usercenter/cloud/user/login"
    
    form_data = {
        "username": username,
        "password": password
    }
    
    try:
        logging.info(f"Attempting fallback login with form data to {login_url}")
        
        response = requests.post(
            login_url,
            data=form_data,
            timeout=30
        )
        
        logging.info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("code") == 0 or result.get("code") == 200:
                logging.info("Fallback login successful!")
                
                token = None
                if "token" in result:
                    token = result["token"]
                elif "data" in result and result["data"] and "token" in result["data"]:
                    token = result["data"]["token"]
                
                if token:
                    logging.info(f"Token received: {token[:10]}...")
                    return True
                else:
                    logging.warning("Login succeeded but no token in response")
            else:
                logging.warning(f"Fallback login failed with code {result.get('code')}: {result.get('msg')}")
        else:
            logging.error(f"Fallback API request failed with status {response.status_code}")
            if response.status_code < 500:  # Only print response text for non-server errors
                logging.error(f"Response: {response.text}")
            
    except Exception as e:
        logging.error(f"Error during fallback API request: {str(e)}")
    
    return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python simple_auth_test.py <username> <password> [base_url]")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    base_url = sys.argv[3] if len(sys.argv) > 3 else "https://monitor.byte-watt.com"
    
    print("\nTesting encryption function...")
    if test_encryption():
        print("✅ Encryption function PASSED")
    else:
        print("❌ Encryption function FAILED")
        sys.exit(1)
    
    print(f"\nTesting API login with {username}...")
    if test_api_login(username, password, base_url):
        print("✅ API login SUCCESSFUL - Authentication works!")
    else:
        print("❌ API login FAILED - Authentication doesn't work")