from operation_drake.ingestion.url_detector import detect_urls, extract_source_url

# ---------------------------------------------------------------------------
# detect_urls (regex fallback)
# ---------------------------------------------------------------------------


def test_detect_urls_finds_plain_link():
    assert detect_urls("check this out https://example.com/page") == ["https://example.com/page"]


def test_detect_urls_returns_empty_when_none_present():
    assert detect_urls("just a plain note, no links here") == []


# ---------------------------------------------------------------------------
# extract_source_url
# ---------------------------------------------------------------------------


def test_extract_source_url_prefers_text_link_entity():
    text = "Read this article"
    entities = [{"type": "text_link", "offset": 5, "length": 4, "url": "https://real-target.com"}]
    assert extract_source_url(text, entities) == "https://real-target.com"


def test_extract_source_url_uses_url_entity_offset():
    text = "Saw this https://example.com/thing today"
    entities = [{"type": "url", "offset": 9, "length": 25}]
    assert extract_source_url(text, entities) == "https://example.com/thing"


def test_extract_source_url_falls_back_to_regex_when_no_entities():
    text = "no entities but a link https://example.org/x"
    assert extract_source_url(text, None) == "https://example.org/x"


def test_extract_source_url_falls_back_to_regex_when_entities_have_no_url_type():
    text = "bold note https://example.org/y"
    entities = [{"type": "bold", "offset": 0, "length": 4}]
    assert extract_source_url(text, entities) == "https://example.org/y"


def test_extract_source_url_returns_none_when_nothing_found():
    assert extract_source_url("just plain text", []) is None


def test_extract_source_url_text_link_wins_over_regex_when_urls_differ():
    """The visible/raw text may contain a different (or no) literal URL than
    the entity's actual target -- the entity must win regardless."""
    text = "Read this: https://display-only.example.com"
    entities = [
        {"type": "text_link", "offset": 0, "length": 4, "url": "https://real-target.example.com"}
    ]
    assert extract_source_url(text, entities) == "https://real-target.example.com"
