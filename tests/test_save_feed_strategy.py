#!/usr/bin/env python3
"""
Test for the saveFeedStrategy ByteWatt API endpoint.

This script queries the current feed strategy list first, displays the active
settings, builds a safe save payload (either performing a test save of existing
settings or executing a safe, temporary modification-and-restore cycle), and
verifies the results.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import requests

# Add the parent directory to the path to enable importing from tests.test_auth
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_feed_strategy import (  # noqa: E402
    login,
    get_inverter_list,
    get_feed_strategy_list,
    print_feed_strategy,
)

# Initialize logging according to project guidelines
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_save_feed_strategy")

# Constants for API paths to avoid magic strings/numbers
DEFAULT_BASE_URL = "https://monitor.byte-watt.com"
API_SAVE_FEED_STRATEGY_PATH = "/api/iterate/sysSet/saveFeedStrategy"
HTTP_SUCCESS_CODE = 200
TIMEOUT_SECONDS = 30


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
    logger.info("Save payload:\n%s", json.dumps(payload, indent=2))
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


def build_save_payload(
    get_response_data: Dict[str, Any],
    system_id: str,
    battery_en: Optional[int] = None,
    cutoff_soc: Optional[float] = None,
    precharge_en: Optional[int] = None,
    dto_list: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Build a saveFeedStrategy payload from the retrieved getFeedStrategyList data.

    Maps feedStrategyVOList to feedStrategyDTOList and overrides specific fields
    if provided.
    """
    # Initialize basic fields with defaults or existing values
    payload = {
        "batteryEn": (
            battery_en if battery_en is not None else get_response_data.get("batteryEn", 0)
        ),
        "batteryFeedCutoffSoc": (
            cutoff_soc if cutoff_soc is not None
            else get_response_data.get("batteryFeedCutoffSoc", 0.0)
        ),
        "id": system_id,
        "prechargeEn": (
            precharge_en if precharge_en is not None else get_response_data.get("prechargeEn", 0)
        ),
    }

    # Construct the DTO list
    constructed_dtos = []
    if dto_list is not None:
        constructed_dtos = dto_list
    else:
        # Automatically map VO list to DTO list
        vo_list = get_response_data.get("feedStrategyVOList", [])
        for vo in vo_list:
            dto = {
                "id": vo.get("id"),
                "sysSn": vo.get("sysSn"),
                "start": vo.get("start"),
                "end": vo.get("end"),
                "feedPower": vo.get("feedPower"),
                "sort": vo.get("sort"),
            }
            # Remove keys with None values to keep the payload clean
            dto = {k: v for k, v in dto.items() if v is not None}
            constructed_dtos.append(dto)

    payload["feedStrategyDTOList"] = constructed_dtos
    return payload


if __name__ == "__main__":
    # Handle parsing of arguments
    parser = argparse.ArgumentParser(
        description="Test ByteWatt saveFeedStrategy API endpoint."
    )
    parser.add_argument("--email", help="ByteWatt account email (overrides .env)")
    parser.add_argument("--password", help="ByteWatt account password (overrides .env)")
    parser.add_argument("--system-id", help="System ID (overrides .env/auto-discovery)")
    parser.add_argument(
        "--action",
        choices=["test-save", "toggle-feed", "set-cutoff", "add-schedule"],
        default="test-save",
        help="Type of save action to test (default: safe test-save of current settings)"
    )
    parser.add_argument(
        "--cutoff-soc",
        type=float,
        help="New cutoff SOC to set (for set-cutoff action)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print save payload without sending")

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    username = args.email or os.getenv("BYTEWATT_EMAIL")
    password = args.password or os.getenv("BYTEWATT_PASSWORD")
    system_id = args.system_id or os.getenv("BYTEWATT_SYSTEM_ID")

    if not username or not password:
        print("Error: Credentials not found in .env, and not provided via arguments.")
        parser.print_help()
        sys.exit(1)

    # Perform authentication
    token = login(username, password)
    if not token:
        print("❌ Authentication failed.")
        sys.exit(1)

    # Discover or resolve system ID
    if not system_id or any(sn_marker in system_id for sn_marker in ("SP", "25000")):
        print("Resolving or discovering system ID via inverter list...")
        inverters = get_inverter_list(token)
        resolved_id = None
        if inverters:
            for inv in inverters:
                sys_sn = inv.get("sysSn")
                sys_id = inv.get("systemId")
                if system_id and sys_sn == system_id:
                    print(f"Resolved serial number '{system_id}' to system ID: '{sys_id}'")
                    resolved_id = sys_id
                    break
                elif not system_id and sys_id:
                    print(f"Auto-discovered system ID: '{sys_id}' for inverter SN: {sys_sn}")
                    resolved_id = sys_id
                    break

            if resolved_id:
                system_id = resolved_id

        if not system_id:
            print("❌ Failed to automatically discover or resolve a system ID.")
            sys.exit(1)

    # 1. Fetch current settings to build base payload
    print("\n--- Step 1: Fetching current settings ---")
    current_settings = get_feed_strategy_list(token, system_id)
    if not current_settings:
        print("❌ Failed to retrieve current settings, aborting save test.")
        sys.exit(1)

    print("Current settings retrieved:")
    print_feed_strategy(current_settings)

    # 2. Build target payload based on specified action
    print("--- Step 2: Building save payload ---")
    payload = {}

    if args.action == "test-save":
        print("Action: Safe test-save (saving back the exact same retrieved settings)")
        payload = build_save_payload(current_settings, system_id)

    elif args.action == "toggle-feed":
        current_en = current_settings.get("batteryEn", 0)
        new_en = 1 if current_en == 0 else 0
        print(f"Action: Safe edit-and-restore cycle (Toggling batteryEn {current_en} -> {new_en})")
        payload = build_save_payload(current_settings, system_id, battery_en=new_en)

    elif args.action == "set-cutoff":
        if args.cutoff_soc is None:
            print("❌ Error: --cutoff-soc must be provided when using --action set-cutoff")
            sys.exit(1)
        print(f"Action: Set batteryFeedCutoffSoc to {args.cutoff_soc}%")
        payload = build_save_payload(current_settings, system_id, cutoff_soc=args.cutoff_soc)

    elif args.action == "add-schedule":
        print("Action: Add/update schedule (09:45 - 10:00, 4000 W, sort 2)")
        payload = build_save_payload(current_settings, system_id)
        dtos = payload["feedStrategyDTOList"]

        # Check if sort 2 schedule already exists, update it if so
        sort_2_found = False
        for dto in dtos:
            if dto.get("sort") == 2:
                dto["start"] = "09:45"
                dto["end"] = "10:00"
                dto["feedPower"] = 4000
                dto["sysSn"] = "25000SP265W00123"
                sort_2_found = True
                break

        if not sort_2_found:
            dtos.append({
                "sysSn": "25000SP265W00123",
                "start": "09:45",
                "end": "10:00",
                "feedPower": 4000,
                "sort": 2
            })

    # Validate dry run
    if args.dry_run:
        print("\n=== DRY RUN MODE: Payload built successfully ===")
        print(json.dumps(payload, indent=2))
        print("=================================================")
        sys.exit(0)

    # 3. Send save request
    print("\n--- Step 3: Sending save request ---")
    success = save_feed_strategy(token, payload)

    if success:
        print("✅ Save feed strategy request succeeded!")

        # If it was a toggle-feed test, let's restore the original state immediately
        if args.action == "toggle-feed":
            print("\n--- Step 4: Restoring original settings (Auto-cleanup) ---")
            original_payload = build_save_payload(current_settings, system_id)
            restore_success = save_feed_strategy(token, original_payload)
            if restore_success:
                print("✅ Original settings restored successfully. Clean run!")
            else:
                print("❌ WARNING: Failed to restore original settings. Please check manually!")
                sys.exit(1)

        # 5. Fetch settings again to confirm changes propagated
        print("\n--- Final Step: Verifying settings on server ---")
        final_settings = get_feed_strategy_list(token, system_id)
        if final_settings:
            print("Verified settings on server:")
            print_feed_strategy(final_settings)
        else:
            print("⚠️ Warning: Could not verify final settings from server.")
    else:
        print("❌ Save feed strategy request failed.")
        sys.exit(1)
