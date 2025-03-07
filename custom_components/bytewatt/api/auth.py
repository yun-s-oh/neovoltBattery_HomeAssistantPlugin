"""Authentication handling for Byte-Watt API."""
import logging
import requests
from typing import Dict, Optional

_LOGGER = logging.getLogger(__name__)


class ByteWattAuth:
    """Authentication handler for Byte-Watt API."""
    
    def __init__(self, username: str, password: str):
        """Initialize with login credentials."""
        self.username = username
        self.password = password
        self.access_token = None
        
        # For signature generation
        self.prefix = "al8e4s"
        self.suffix = "ui893ed"
        
    def get_auth_signature(self, is_login=False):
        """
        Generate a dynamic auth signature.
        
        Args:
            is_login: True for login endpoint, False for other API endpoints
        
        Returns:
            A dynamically generated authentication signature
        """
        # Choose modifier based on endpoint type
        modifier = 'd' if is_login else 'e'
        
        # Create a pattern for the middle part (128 characters)
        middle_part = ""
        for i in range(128):
            # Simple pattern that creates a pseudo-random but consistent string
            c = "0123456789abcdef"[i % 16]
            middle_part += c
        
        # Combine all parts to create the final signature
        signature = f"{self.prefix}{modifier}{middle_part}{self.suffix}"
        return signature
    
    def get_token(self, session: requests.Session, base_url: str) -> bool:
        """
        Get an authentication token.
        
        Args:
            session: Requests session to use
            base_url: Base URL for the API
            
        Returns:
            True if token was obtained successfully, False otherwise
        """
        try:
            # Generate dynamic signature for login
            auth_signature = self.get_auth_signature(is_login=True)
            login_url = f"{base_url}/api/Account/Login?authsignature={auth_signature}&authtimestamp=11111"
            
            payload = {
                "username": self.username,
                "password": self.password
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            _LOGGER.debug(f"Sending login request with dynamic signature")
            
            response = session.post(login_url, json=payload, headers=headers)
            
            _LOGGER.debug(f"Login response status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "data" in data and "AccessToken" in data["data"]:
                        self.access_token = data["data"]["AccessToken"]
                        _LOGGER.debug(f"Successfully obtained token: {self.access_token[:10]}...")
                        return True
                    else:
                        _LOGGER.error(f"Token not found in response: {data}")
                except Exception as e:
                    _LOGGER.error(f"Error parsing login response: {e}")
            else:
                try:
                    _LOGGER.error(f"Login failed with status {response.status_code}: {response.text}")
                except:
                    _LOGGER.error(f"Login failed with status {response.status_code}")
            
            return False
        except Exception as e:
            _LOGGER.error(f"Error in login: {e}")
            return False
    
    def set_auth_headers(self) -> Dict[str, str]:
        """
        Set authentication headers for an API request.
        
        Returns:
            Dictionary of headers to use with API requests
        """
        # Generate dynamic signature for API calls
        auth_signature = self.get_auth_signature(is_login=False)
        
        headers = {
            "Content-Type": "application/json",
            "authtimestamp": "11111",
            "authsignature": auth_signature
        }
        
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        return headers