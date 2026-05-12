---
name: auth-handshake
description: ByteWatt API authentication using AES-CBC encrypted passwords. Use when implementing or debugging login flows.
---

# Authentication Handshake

## Description

How to properly authenticate against the ByteWatt API.

## Key Files

- `custom_components/bytewatt/api/neovolt_client.py`
- `tests/test_auth.py`

## Pattern

1. Derive the AES **key** from the username using SHA-256 (32 bytes).
2. Derive the AES **IV** from the username using MD5 (16 bytes).
3. Pad the plaintext password using PKCS#7 to 16-byte blocks.
4. Encrypt using **AES-CBC** mode.
5. Base64-encode the ciphertext.
6. Send the encrypted password along with the username to:
   ```
   POST /api/usercenter/cloud/user/login
   ```
7. Extract the `token` from the JSON response (`data.token` or top-level `token`).

## Example

```python
from Crypto.Cipher import AES
import hashlib, base64

key = hashlib.sha256(username.encode("utf-8")).digest()
iv = hashlib.md5(username.encode("utf-8")).digest()

data = password.encode("utf-8")
pad_len = AES.block_size - (len(data) % AES.block_size)
data += bytes([pad_len]) * pad_len

cipher = AES.new(key, AES.MODE_CBC, iv)
encrypted = base64.b64encode(cipher.encrypt(data)).decode("ascii")
```
