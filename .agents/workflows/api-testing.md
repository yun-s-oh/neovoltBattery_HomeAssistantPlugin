---
description: How to create and run API test scripts using .env credentials
---

# Creating API Test Scripts

This workflow outlines the standard procedure for creating and running test scripts for the ByteWatt API in the `tests/` directory.

## 1. Prerequisites

All test scripts should authenticate against the ByteWatt API using the credentials defined in your local `.env` file. Do not hardcode credentials or rely exclusively on command-line arguments.

We use `python-dotenv` to load environment variables.

Ensure your `.env` file in the project root looks like this:
```env
BYTEWATT_EMAIL="your_email@example.com"
BYTEWATT_PASSWORD="your_password"
```

If you don't have the `dotenv` package installed in your environment, you can install it:
```bash
pip install python-dotenv requests pycryptodome
```

## 2. Test Script Structure

When creating a new test script (e.g., `tests/test_new_endpoint.py`), follow this general structure:

1. **Load `.env`**: Load the environment variables at the start.
2. **Import Encryption**: Import the `encrypt_password` function from `test_auth.py`.
3. **Login**: Perform a login to obtain an authentication token.
4. **Call API**: Use the token to call the desired endpoint.
5. **Output**: Print or assert the results.

### Boilerplate Template

```python
#!/usr/bin/env python3
"""
Test for the new ByteWatt API endpoint.
"""
import sys
import os
import logging
import json
import requests
from dotenv import load_dotenv

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_auth import encrypt_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def login(username, password, base_url="https://monitor.byte-watt.com"):
    # Login logic similar to test_battery_data.py
    # ...
    pass

def test_my_endpoint(token, base_url="https://monitor.byte-watt.com"):
    # Endpoint logic
    pass

if __name__ == "__main__":
    # Load environment variables from .env file
    load_dotenv()
    
    username = os.getenv("BYTEWATT_EMAIL")
    password = os.getenv("BYTEWATT_PASSWORD")
    
    # Optional fallback to command line arguments
    if not username or not password:
        if len(sys.argv) < 3:
            print("Error: BYTEWATT_EMAIL and BYTEWATT_PASSWORD not found in .env, and not provided via CLI.")
            print(f"Usage: python {sys.argv[0]} [username] [password]")
            sys.exit(1)
        username = sys.argv[1]
        password = sys.argv[2]

    # Perform the test
    token = login(username, password)
    if token:
        test_my_endpoint(token)
```

## 3. Running the Tests

Once created, you can run the test script directly from the command line without providing credentials:

```bash
python tests/test_new_endpoint.py
```
