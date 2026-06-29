import re

import httpx

from personal_agent_os.content.base import ContentAdapter, ContentResult
from personal_agent_os.observability.logging import get_logger

logger = get_logger(__name__)

_AUTH_PATTERNS = ["accounts.google", "login", "signin", "auth", "paywall", "subscribe"]


class WebpageAdapter(ContentAdapter):
    def can_handle(self, url: str) -> bool:
        return url.startswith("http") and "youtube.com" not in url and "youtu.be" not in url

    def extract(self, url: str) -> ContentResult:
        try:
            if any(p in url.lower() for p in _AUTH_PATTERNS):
                return ContentResult(url=url, blocked=True, block_reason="URL pattern suggests authentication wall")
            resp = httpx.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code in (401, 403, 407):
                return ContentResult(url=url, blocked=True, block_reason=f"HTTP {resp.status_code} — authentication required")
            text = resp.text
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = " ".join(text.split())[:8000]
            title_match = re.search(r"<title[^>]*>(.*?)</title>", resp.text, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else url
            return ContentResult(url=url, title=title, text=text)
        except Exception as e:
            logger.warning({"action": "webpage_extract_failed", "url": url, "error": str(e)})
            return ContentResult(url=url, error=str(e))
