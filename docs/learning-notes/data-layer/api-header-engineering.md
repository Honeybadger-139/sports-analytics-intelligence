# API Header Engineering & NBA API Resilience

> **Concept**: Modern web APIs (like NBA.com) often implement security measures to block automated traffic. Header engineering is an operational fallback strategy for cases where the upstream client library needs patching.

## What is it?
Header engineering involves configuring request metadata to match patterns expected from real browser sessions when default client behavior is blocked.

## Why does it matter?
If requests are fingerprinted as bots, calls may fail with `403`, `429`, or timeouts. This is why the pipeline prioritizes resilience controls (rate limiting, retry/backoff, health checks) and keeps header patching as a documented contingency.

## How it works (The Intuition)

When you visit a site, your browser sends a complex set of "handshake" information. To bypass blocks, we must replicate:

1.  **User-Agent**: The identity of your browser (e.g., "Chrome 121 on Windows 10").
2.  **Referer/Origin**: Where the request is coming from. The NBA API often checks if you "arrived" from `www.nba.com`.
3.  **Client Hints (`Sec-Ch-Ua`)**: Modern Chrome headers that provide detailed browser metadata.
4.  **Security Tokens**: Custom headers (like `x-nba-stats-token`) that the site's own JavaScript uses.

### Current Repo Status
- The ingestion module currently calls `nba_api` endpoints directly and does not contain explicit in-repo custom header injection.
- This note documents the fallback strategy used when upstream API behavior changes.

## Reference Pattern: Before vs. After

### Junior Approach (The "Default" way)
```python
import requests
# This often fails!
response = requests.get("https://stats.nba.com/stats/teamgamelog") 
```

### Fallback Approach (Header Engineering)
```python
headers = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "x-nba-stats-token": "true",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site"
}
response = requests.get(url, headers=headers)
```

## Common Interview Questions

1.  **"What do you do when an API starts blocking your ingestion jobs?"**
    - *Answer*: First, verify and update the client library. If blocked behavior persists, inspect browser requests and apply a targeted patch strategy with explicit headers as a temporary mitigation.

2.  **"Why use manual patches instead of a proxy?"**
    - *Answer*: Proxies solve IP-based blocking but don't solve header-based fingerprinting. If your headers identify you as a bot, it doesn't matter what IP you use — you'll still be blocked. Solving headers is the "root" fix; proxies are for distributed rate limiting.

## Senior Manager / Architect Perspective
"An architect cares about data-source fragility. The production baseline is resilient retries, rate limiting, and auditing. Header patching is documented as a controlled fallback, not assumed as always-active code."
