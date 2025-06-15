"""Validation logic for ByteWatt data.

The new API is trusted to provide accurate data, so validation is minimal.
"""
import logging
from typing import Dict, Any, Tuple, Optional

_LOGGER = logging.getLogger(__name__)


class DataValidator:
    """Minimal validator that performs basic sanity checks on data."""
    
    def __init__(self):
        """Initialize the validator."""
        _LOGGER.info("Data validator initialized - minimal validation enabled")
        
    def is_valid_response(self, data: Dict[str, Any], timestamp: Optional[float] = None) -> Tuple[bool, Optional[str]]:
        """
        Perform minimal validation on API response data.
        
        Args:
            data: The data to validate
            timestamp: Unix timestamp of the data (optional)
            
        Returns:
            (is_valid, reason_if_invalid)
        """
        # Basic sanity check - ensure we have data
        if not data:
            return False, "No data provided"
            
        # Check for required fields
        if 'soc' not in data:
            return False, "Missing SOC value"
            
        # Basic range check for SOC
        soc = data.get('soc')
        if soc is None or soc < 0 or soc > 100:
            return False, f"Invalid SOC value: {soc}"
            
        return True, None


# For backwards compatibility
BalancedAdvancedValidator = DataValidator
NeuralPhysicsValidator = DataValidator
EnergyDataValidator = DataValidator