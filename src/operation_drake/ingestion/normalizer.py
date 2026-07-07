import hashlib
from dataclasses import dataclass, field

from operation_drake.ingestion.url_detector import detect_urls

UNTRUSTED_MESSAGE_TYPES = {"forwarded", "document"}


def compute_message_hash(normalized_text: str) -> str:
    """SHA-256 of the normalized message content, lowercase and whitespace-collapsed."""
    canonical = " ".join(normalized_text.lower().split())
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class NormalizedMessage:
    raw_text: str
    normalized_text: str
    message_type: str
    detected_urls: list[str] = field(default_factory=list)
    is_untrusted_content: bool = False
    metadata: dict = field(default_factory=dict)


def normalize_message(
    raw: str,
    message_type: str,
    forwarded_from: str | None = None,
) -> NormalizedMessage:
    normalized = raw.strip()
    urls = detect_urls(normalized)
    effective_type = message_type
    if message_type == "text" and urls and normalized in urls:
        effective_type = "url"
    is_untrusted = message_type in UNTRUSTED_MESSAGE_TYPES or forwarded_from is not None
    return NormalizedMessage(
        raw_text=raw,
        normalized_text=normalized,
        message_type=effective_type,
        detected_urls=urls,
        is_untrusted_content=is_untrusted,
    )
