#!/usr/bin/env python3
"""
Test for the new inverter_list API endpoint.

This test verifies that the getCustomMenuEssList endpoint works.
"""
import sys
import os
import logging
import json
import requests
from datetime import datetime

# Add the parent directory to the path so we can import for test_auth.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the encryption function from test_auth.py
from tests.test_auth import encrypt_password

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_inverter_list")

def login(username: str, password: str, base_url: str = "https://monitor.byte-watt.com") -> str:
    """Log in to the API and return the authentication token."""
    login_url = f"{base_url}/api/usercenter/cloud/user/login"
    
    # Encrypt the password
    encrypted_password = encrypt_password(password, username)
    
    # Create payload
    payload = {
        "username": username,
        "password": encrypted_password
    }
    
    logger.info(f"Logging in to {login_url}")
    
    try:
        response = requests.post(
            login_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Login failed with status {response.status_code}: {response.text}")
            return None
        
        result = response.json()
        
        if result.get("code") != 0 and result.get("code") != 200:
            logger.error(f"Login failed with code {result.get('code')}: {result.get('msg')}")
            return None
        
        # Extract token
        token = None
        if "token" in result:
            token = result["token"]
        elif "data" in result and result["data"] and "token" in result["data"]:
            token = result["data"]["token"]
        
        if token:
            logger.info(f"Login successful, token: {token[:10]}...")
            return token
        else:
            logger.error("No token found in response")
            return None
    
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        return None

def get_inverter_list(token: str, base_url: str = "https://monitor.byte-watt.com") -> dict:
    """Get inverter_list using the new API endpoint."""
    url = f"{base_url}/api/stable/home/getCustomMenuEssList"
    
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "language": "en-US",
        "operationDate": current_date,
        "platform": "AK9D8H",
        "System": "alphacloud"
    }
    
    logger.info(f"Getting inverter_list from {url}")
    
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to get inverter_list with status {response.status_code}: {response.text}")
            return None
        
        result = response.json()
        
        if result.get("code") != 0 and result.get("code") != 200:
            logger.error(f"Failed to get inverter_list with code {result.get('code')}: {result.get('msg')}")
            return None
        
        data = result.get("data")
        logger.info(f"Received inverter_list: {json.dumps(data, indent=2)}")
        return data
    
    except Exception as e:
        logger.error(f"Error getting inverter_list: {str(e)}")
        return None

def print_inverter_list(data: dict) -> None:
    """Print the important battery values in a readable format."""
    if not data:
        print("No inverter list available")
        return
     
    print("\n=== Inverter List ===")
    for key in data:
        print(f"sysSn: {key['sysSn']}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_inverter_list.py <username> <password>")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    
    # Login to get token
    token = login(username, password)
    
    if not token:
        print("❌ Authentication failed, cannot test inverter list")
        sys.exit(1)
    
    # Get inverter_list
    inverter_list = get_inverter_list(token)
    
    if inverter_list:
        print("✅ Successfully retrieved inverter list!")
        print_inverter_list(inverter_list)
    else:
        print("❌ Failed to retrieve inverter list")