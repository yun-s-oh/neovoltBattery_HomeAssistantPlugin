---
name: circuit-breaker
description: Resilient API call pattern using circuit breaker to handle outages. Use when wrapping external HTTP requests.
---

# Circuit Breaker Pattern

## Description

Managing API request failures to avoid rate limits or IP bans during outages.

## Key Files

- `utilities/circuit_breaker.py`

## Pattern

- Wrap all external HTTP requests in the circuit breaker.
- If successive failures exceed a threshold, the circuit **opens** and blocks further requests for a cooldown period.
- After the cooldown, the circuit enters a **half-open** state allowing a single test request.
- If the test request succeeds, the circuit **closes** and normal operation resumes.

## Usage

All calls to `monitor.byte-watt.com` should be routed through the circuit breaker to prevent flooding the API during sustained outages.
