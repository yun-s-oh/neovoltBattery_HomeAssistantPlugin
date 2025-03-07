"""Base client for Byte-Watt API with retry logic."""
import logging
import requests
import time
from typing import Optional, Any, Dict, Callable, TypeVar

from .auth import ByteWattAuth

_LOGGER = logging.getLogger(__name__)

T = TypeVar('T')


class ByteWattAPIClient:
    """Base client for Byte-Watt API with retry logic."""
    
    def __init__(self, username: str, password: str):
        """Initialize the API client."""
        self.base_url = "https://monitor.byte-watt.com"
        self.session = requests.Session()
        self.auth = ByteWattAuth(username, password)
    
    def ensure_authenticated(self) -> bool:
        """
        Ensure the client is authenticated.
        
        Returns:
            True if authenticated, False otherwise
        """
        if not self.auth.access_token:
            return self.auth.get_token(self.session, self.base_url)
        return True
    
    def _api_request(self, 
                    method: str, 
                    endpoint: str, 
                    max_retries: int = 5, 
                    retry_delay: int = 1,
                    data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Make an API request with retry capability.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            data: Optional data to send with the request
            
        Returns:
            API response data if successful, None otherwise
        """
        if not self.ensure_authenticated():
            return None
        
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(max_retries):
            try:
                headers = self.auth.set_auth_headers()
                
                _LOGGER.debug(f"{method} request to {endpoint} attempt {attempt+1}/{max_retries}")
                
                if method.upper() == "GET":
                    response = self.session.get(url, headers=headers, timeout=10)
                elif method.upper() == "POST":
                    response = self.session.post(url, json=data, headers=headers, timeout=10)
                else:
                    _LOGGER.error(f"Unsupported HTTP method: {method}")
                    return None
                
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        
                        # Check for network exception
                        if "code" in response_data and response_data["code"] == 9007:
                            _LOGGER.warning(f"Network exception from server (attempt {attempt+1}/{max_retries}): {response_data['info']}")
                            # Server is reporting a network issue, let's retry
                            time.sleep(retry_delay)
                            continue
                            
                        return response_data
                    except Exception as e:
                        _LOGGER.error(f"Error parsing response data (attempt {attempt+1}/{max_retries}): {e}")
                elif response.status_code == 401:
                    _LOGGER.info("Token expired, refreshing...")
                    self.auth.access_token = None
                    if not self.ensure_authenticated():
                        _LOGGER.error("Failed to refresh token")
                        return None
                else:
                    _LOGGER.error(f"Request failed with status {response.status_code} (attempt {attempt+1}/{max_retries})")
                
                # Wait before retrying
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
            except Exception as e:
                _LOGGER.error(f"Exception during request (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        _LOGGER.error(f"Failed to make request after {max_retries} attempts")
        return None
    
    def with_retry(self, 
                  func: Callable[..., T], 
                  max_retries: int = 5, 
                  retry_delay: int = 1, 
                  *args, 
                  **kwargs) -> Optional[T]:
        """
        Execute a function with retry capability.
        
        Args:
            func: Function to execute
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            args: Positional arguments to pass to the function
            kwargs: Keyword arguments to pass to the function
            
        Returns:
            Function result if successful, None otherwise
        """
        for attempt in range(max_retries):
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                _LOGGER.error(f"Error executing function (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        _LOGGER.error(f"Failed to execute function after {max_retries} attempts")
        return None
    
    def get(self, endpoint: str, max_retries: int = 5, retry_delay: int = 1) -> Optional[Dict[str, Any]]:
        """
        Make a GET request to the API.
        
        Args:
            endpoint: API endpoint
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            API response data if successful, None otherwise
        """
        return self._api_request("GET", endpoint, max_retries, retry_delay)
    
    def post(self, 
            endpoint: str, 
            data: Dict[str, Any], 
            max_retries: int = 5, 
            retry_delay: int = 1) -> Optional[Dict[str, Any]]:
        """
        Make a POST request to the API.
        
        Args:
            endpoint: API endpoint
            data: Data to send with the request
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            API response data if successful, None otherwise
        """
        return self._api_request("POST", endpoint, max_retries, retry_delay, data)