"""Session and header management for Instagram scraping."""
import os
import random
import time
from typing import Dict

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 342.0.0.32.109",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

DEFAULT_IG_APP_ID = "936619743392459"


class SessionManager:
    """Provides randomized headers, backoff delays, and session handling."""

    def __init__(self, min_delay: float = 1.5, max_delay: float = 4.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._last_request_time = 0.0

    def get_random_user_agent(self) -> str:
        return random.choice(USER_AGENTS)

    def get_public_headers(self) -> Dict[str, str]:
        """Headers required for Instagram public web endpoints."""
        return {
            "User-Agent": self.get_random_user_agent(),
            "X-IG-App-ID": DEFAULT_IG_APP_ID,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "*/*",
            "Origin": "https://www.instagram.com",
            "Referer": "https://www.instagram.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    def polite_delay(self):
        """Throttle requests to prevent rapid-fire IP rate-limiting."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        target_delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < target_delay:
            time.sleep(target_delay - elapsed)
        self._last_request_time = time.monotonic()
