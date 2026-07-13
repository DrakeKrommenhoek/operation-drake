import re

_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def detect_urls(text: str) -> list[str]:
    return _URL_PATTERN.findall(text)


def extract_source_url(text: str, entities: list[dict] | None = None) -> str | None:
    """Resolve the message's source URL independent of content type or
    classification outcome. Telegram message entities are authoritative --
    a "text_link" entity carries an explicit target url that can differ
    from the display text, so it is checked first. A "url" entity confirms
    a plain link at a known offset. A regex scan of the raw text is the
    fallback for content with no entity metadata at all."""
    for entity in entities or []:
        if entity.get("type") == "text_link" and entity.get("url"):
            return entity["url"]
    for entity in entities or []:
        if entity.get("type") == "url":
            offset, length = entity.get("offset"), entity.get("length")
            if isinstance(offset, int) and isinstance(length, int):
                return text[offset : offset + length]
    urls = detect_urls(text)
    return urls[0] if urls else None
