---
description: Guidelines for robust error handling across the integration
---

# Error Handling & Best Practices

Guidelines for robust error handling across the integration.

## Rules

- Use specific exception types from the API layers rather than generic exceptions.
- Implement retry logic with exponential backoff for transient API failures.
- Ensure the circuit breaker (`utilities/circuit_breaker.py`) is used for external API calls to prevent flooding during outages.
- Log at the appropriate severity level and provide meaningful error messages for users.
