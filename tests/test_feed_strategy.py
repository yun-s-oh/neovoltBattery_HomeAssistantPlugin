#!/usr/bin/env python3
"""
Test for the getFeedStrategyList ByteWatt API endpoint.

This script authenticates with the ByteWatt API using credentials from the .env file,
fetches the list of inverters to discover the system ID (or uses a provided one),
and queries the feed-in strategy settings.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import requests

# Add the parent directory to the path to enable importing from tests.test_auth
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_auth import encrypt_password  # noqa: E402

# Initialize logging according to project guidelines
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_feed_strategy")

# Constants for API paths to avoid magic strings/numbers
DEFAULT_BASE_URL = "https://monitor.byte-watt.com"
API_LOGIN_PATH = "/api/usercenter/cloud/user/login"
API_INVERTER_LIST_PATH = "/api/stable/home/getCustomMenuEssList"
API_FEED_STRATEGY_PATH = "/api/iterate/sysSet/getFeedStrategyList"
API_SAVE_FEED_STRATEGY_PATH = "/api/iterate/sysSet/saveFeedStrategy"
HTTP_SUCCESS_CODE = 200
TIMEOUT_SECONDS = 30


def login(
    username: str,
    password: str,
    base_url: str = DEFAULT_BASE_URL,
) -> Optional[str]:
    """
    Log in to the ByteWatt API and return the authentication token.

    Uses AES encryption on the password prior to sending the request.
    """
    login_url = f"{base_url}{API_LOGIN_PATH}"
    encrypted_password = encrypt_password(password, username)
    payload = {"username": username, "password": encrypted_password}

    logger.info("Attempting login to %s", login_url)
    try:
        response = requests.post(
            login_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT_SECONDS,
        )

        if response.status_code != HTTP_SUCCESS_CODE:
            logger.error(
                "Login failed with HTTP status %d: %s",
                response.status_code,
                response.text
            )
            return None

        result = response.json()
        if result.get("code") not in (0, HTTP_SUCCESS_CODE):
            logger.error(
                "Login failed with business code %s: %s",
                result.get("code"),
                result.get("msg")
            )
            return None

        token = None
        if "token" in result:
            token = result["token"]
        elif "data" in result and result["data"] and "token" in result["data"]:
            token = result["data"]["token"]

        if token:
            logger.info("Login successful. Token acquired (prefix: %s...)", token[:10])
            return token

        logger.error("Authentication succeeded but no token was found in the response")
        return None

    except Exception as e:
        logger.exception("Unexpected error occurred during login sequence: %s", str(e))
        return None


def get_inverter_list(
    token: str,
    base_url: str = DEFAULT_BASE_URL,
) -> Optional[List[Dict[str, Any]]]:
    """
    Query the inverter list API endpoint to discover connected systems and their IDs.
    """
    url = f"{base_url}{API_INVERTER_LIST_PATH}"
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "language": "en-US",
        "operationDate": current_date,
        "platform": "AK9D8H",
        "System": "alphacloud",
    }

    logger.info("Requesting inverter list from %s", url)
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)

        if response.status_code != HTTP_SUCCESS_CODE:
            logger.error(
                "Failed to query inverter list (HTTP %d): %s",
                response.status_code,
                response.text
            )
            return None

        result = response.json()
        if result.get("code") not in (0, HTTP_SUCCESS_CODE):
            logger.error(
                "Inverter list API error: code %s, msg: %s",
                result.get("code"),
                result.get("msg")
            )
            return None

        data = result.get("data")
        if isinstance(data, list):
            logger.info("Successfully retrieved %d inverter(s) from API", len(data))
            return data

        logger.error("Unexpected inverter list data format returned by server")
        return None

    except Exception as e:
        logger.exception("Unexpected error querying inverter list: %s", str(e))
        return None


def get_feed_strategy_list(
    token: str,
    system_id: str,
    base_url: str = DEFAULT_BASE_URL,
) -> Optional[Dict[str, Any]]:
    """
    Query the getFeedStrategyList API endpoint for the given system ID.
    """
    url = f"{base_url}{API_FEED_STRATEGY_PATH}"
    params = {"id": system_id}
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "language": "en-US",
        "operationDate": current_date,
        "platform": "AK9D8H",
        "System": "alphacloud",
    }

    logger.info("Requesting feed strategy list from %s?id=%s", url, system_id)
    try:
        response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS)

        if response.status_code != HTTP_SUCCESS_CODE:
            logger.error(
                "Failed to query feed strategy (HTTP %d): %s",
                response.status_code,
                response.text
            )
            return None

        result = response.json()
        if result.get("code") not in (0, HTTP_SUCCESS_CODE):
            logger.error(
                "Feed strategy API error: code %s, msg: %s",
                result.get("code"),
                result.get("msg")
            )
            return None

        data = result.get("data")
        logger.info("Successfully retrieved feed strategy details")
        return data

    except Exception as e:
        logger.exception("Unexpected error querying feed strategy: %s", str(e))
        return None


def save_feed_strategy(
    token: str,
    payload: Dict[str, Any],
    base_url: str = DEFAULT_BASE_URL,
) -> bool:
    """
    Save the feed strategy settings via POST request to the API.

    Returns True if the API returns a successful business code and data is True.
    """
    url = f"{base_url}{API_SAVE_FEED_STRATEGY_PATH}"
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "language": "en-US",
        "operationDate": current_date,
        "platform": "AK9D8H",
        "System": "alphacloud",
    }

    logger.info("Sending save feed strategy request to %s", url)
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)

        if response.status_code != HTTP_SUCCESS_CODE:
            logger.error(
                "Failed to save feed strategy (HTTP %d): %s",
                response.status_code,
                response.text
            )
            return False

        result = response.json()
        if result.get("code") not in (0, HTTP_SUCCESS_CODE):
            logger.error(
                "Save feed strategy API error: code %s, msg: %s",
                result.get("code"),
                result.get("msg")
            )
            return False

        data = result.get("data")
        if data is True:
            logger.info("Successfully saved feed strategy settings!")
            return True

        logger.error("Save feed strategy returned unexpected data: %s", data)
        return False

    except Exception as e:
        logger.exception("Unexpected error saving feed strategy: %s", str(e))
        return False


def print_feed_strategy(data: Dict[str, Any]) -> None:
    """
    Display the feed strategy settings in a formatted, highly readable structure.
    """
    if not data:
        print("No feed strategy data available to display")
        return

    print("\n" + "=" * 50)
    print("                FEED-IN STRATEGY SETTINGS")
    print("=" * 50)
    print(f"Battery Enabled (batteryEn):             {data.get('batteryEn')}")
    print(f"Cutoff SOC (batteryFeedCutoffSoc):       {data.get('batteryFeedCutoffSoc')}%")
    print(f"Inverter Max Power (poinv):              {data.get('poinv')} W")
    print(f"Time Period Limit (timePeriodLimit):     {data.get('timePeriodLimit')}")
    print(f"Battery Use Capacity (batUseCap):        {data.get('batUseCap')}%")
    print(f"Precharge Enabled (prechargeEn):         {data.get('prechargeEn')}")
    print(f"Precharge SOC (prechargeSoc):            {data.get('prechargeSoc')}%")
    print("-" * 50)

    strategies = data.get("feedStrategyVOList", [])
    if strategies:
        print(f"Feed-In Strategy Schedules ({len(strategies)} active):")
        for i, strat in enumerate(strategies, start=1):
            print(f"  Schedule #{i}:")
            print(f"    ID:          {strat.get('id')}")
            print(f"    System SN:   {strat.get('sysSn')}")
            print(f"    Start Time:  {strat.get('start')}")
            print(f"    End Time:    {strat.get('end')}")
            print(f"    Feed Power:  {strat.get('feedPower')}%")
            print(f"    Sort Order:  {strat.get('sort')}")
            print("-" * 30)
    else:
        print("No feed strategy schedules defined.")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    # Load settings from local environment file
    load_dotenv()

    username = os.getenv("BYTEWATT_EMAIL")
    password = os.getenv("BYTEWATT_PASSWORD")
    system_id = os.getenv("BYTEWATT_SYSTEM_ID")

    # Command line argument handling for flexibility
    if len(sys.argv) >= 3:
        username = sys.argv[1]
        password = sys.argv[2]
        if len(sys.argv) > 3:
            system_id = sys.argv[3]
    elif not username or not password:
        print("Error: Credentials not found in .env, and not provided via CLI.")
        print(f"Usage: python {sys.argv[0]} [username] [password] [system_id]")
        sys.exit(1)

    # Begin the authentication flow
    token = login(username, password)
    if not token:
        print("❌ Authentication failed. Please check your credentials.")
        sys.exit(1)

    # Automatically discover the system ID if it wasn't explicitly supplied
    if not system_id:
        print("System ID not provided. Fetching inverter list for auto-discovery...")
        inverters = get_inverter_list(token)
        if inverters:
            # Look for the first inverter with a valid systemId
            for inv in inverters:
                sys_sn = inv.get("sysSn")
                sys_id = inv.get("systemId")
                if sys_id:
                    print(f"Found system ID: '{sys_id}' for inverter SN: {sys_sn}")
                    system_id = sys_id
                    break

        if not system_id:
            print("❌ Failed to automatically discover a system ID.")
            print(
                "Please specify a system ID via environment variable or command line argument."
            )
            sys.exit(1)

    # Perform the endpoint query
    feed_data = get_feed_strategy_list(token, system_id)
    if feed_data:
        print("✅ Successfully retrieved feed strategy data!")
        print_feed_strategy(feed_data)
    else:
        print("❌ Failed to retrieve feed strategy data.")
        sys.exit(1)
