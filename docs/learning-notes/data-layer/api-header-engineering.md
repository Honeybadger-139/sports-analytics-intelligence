# API Header Engineering & Bot Detection Evasion

> **Concept**: Modern web APIs (like NBA.com) often implement security measures to block automated scrapers. "Header Engineering" is the process of crafting HTTP requests that are indistinguishable from legitimate browser sessions.

## What is it?
Header Engineering involves configuring the metadata of an HTTP request (the "headers") to match the specific patterns a website expects from a human user using a real browser (Chrome, Firefox, etc.).

## Why does it matter?
Websites use Bot Detection (like Akamai, Cloudflare, or custom NBA security) to protect their data. If your headers look like a script (e.g., using `python-requests` default User-Agent), you get blocked with `403 Forbidden`, `429 Too Many Requests`, or connection timeouts.

## How it works (The Intuition)

When you visit a site, your browser sends a complex set of "handshake" information. To bypass blocks, we must replicate:

1.  **User-Agent**: The identity of your browser (e.g., "Chrome 121 on Windows 10").
2.  **Referer/Origin**: Where the request is coming from. The NBA API often checks if you "arrived" from `www.nba.com`.
3.  **Client Hints (`Sec-Ch-Ua`)**: Modern Chrome headers that provide detailed browser metadata.
4.  **Security Tokens**: Custom headers (like `x-nba-stats-token`) that the site's own JavaScript uses.

### The "Awe Moment" for Interviews
> "I don't just 'scrape' data; I engineer my ingestion pipeline to respect the site's security context by backporting modern browser headers into our requests. This reduced our API failure rate from 80% to 0%."

## Implementation: Before vs. After

### Junior Approach (The "Default" way)
```python
import requests
# This often fails!
response = requests.get("https://stats.nba.com/stats/teamgamelog") 
```

### Senior Approach (Header Engineering)
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

1.  **"What do you do when an API starts blocking your scraper?"**
    - *Answer*: First, check if the library you're using is outdated. Often, site security changes and libraries need updates. If to update isn't possible (e.g., version mismatch), I perform a header analysis using browser DevTools (Network tab) to see what headers a real browser sends, and then I manually engineer those into my code.

2.  **"Why use manual patches instead of a proxy?"**
    - *Answer*: Proxies solve IP-based blocking but don't solve header-based fingerprinting. If your headers identify you as a bot, it doesn't matter what IP you use — you'll still be blocked. Solving headers is the "root" fix; proxies are for distributed rate limiting.

## Senior Manager / Architect Perspective
"An architect cares about the **fragility** of data sources. When a dependency like `nba_api` breaks, a junior developer might wait for a library fix. A senior engineer understands the underlying HTTP protocol well enough to patch the library themselves and keep the business logic running. This is about **Operational Resilience**."
