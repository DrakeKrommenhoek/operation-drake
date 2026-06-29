from operation_drake.content.base import ContentAdapter, ContentResult


class YouTubeAdapter(ContentAdapter):
    def can_handle(self, url: str) -> bool:
        return "youtube.com" in url or "youtu.be" in url

    def extract(self, url: str) -> ContentResult:
        return ContentResult(
            url=url,
            blocked=True,
            block_reason="YouTube content requires transcript API. Not configured in v1. URL preserved — provide transcript manually.",
        )
