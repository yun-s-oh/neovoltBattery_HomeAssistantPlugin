"""Authentication module for Neovolt API."""
import logging
import hashlib
import base64
from typing import Optional

try:
    from Crypto.Cipher import AES
except ImportError:
    logging.getLogger(__name__).error("PyCryptodome not installed. Install with: pip install pycryptodome")

_LOGGER = logging.getLogger(__name__)

def encrypt_password(password: str, username: str) -> str:
    """
    Encrypt password using the Neovolt API method.
    
    The encryption uses:
    - Key: SHA-256 hash of username
    - IV: MD5 hash of username
    - AES-CBC mode with PKCS7 padding
    - Base64 encoding of the final encrypted data
    
    Args:
        password: The clear-text password
        username: The username (used for key derivation)
        
    Returns:
        Base64-encoded encrypted password
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
        _LOGGER.error("Error encrypting password: %s", str(e))
        return ""