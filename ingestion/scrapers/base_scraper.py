"""Base scraper with retry logic, rate limiting, and Playwright setup."""
from __future__ import annotations

import asyncio
import random
from typing import Any

from playwright.async_api import Browser, async_playwright

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

RATE_LIMIT_DELAY = (1.5, 3.5)  # seconds between requests


async def get_browser() -> Browser:
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    )
    return browser


async def get_page_html(url: str, browser: Browser, retries: int = 3) -> str | None:
    ua = random.choice(USER_AGENTS)
    for attempt in range(retries):
        ctx = await browser.new_context(
            user_agent=ua,
            viewport={"width": 1280, "height": 800},
            locale="en-IE",
        )
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(*RATE_LIMIT_DELAY))
            return await page.content()
        except Exception as e:
            if attempt == retries - 1:
                print(f"Failed to load {url}: {e}")
                return None
            await asyncio.sleep(2 ** attempt)
        finally:
            await ctx.close()
    return None
