import re

_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def detect_urls(text: str) -> list[str]:
    return _URL_PATTERN.findall(text)
