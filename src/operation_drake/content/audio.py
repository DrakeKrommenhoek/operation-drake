from operation_drake.content.base import ContentAdapter, ContentResult

_AUDIO_EXTENSIONS = (".ogg", ".mp3", ".wav", ".m4a", ".opus", ".flac")


class AudioAdapter(ContentAdapter):
    def can_handle(self, url: str) -> bool:
        return any(url.lower().endswith(ext) for ext in _AUDIO_EXTENSIONS)

    def extract(self, url: str) -> ContentResult:
        return ContentResult(
            url=url,
            blocked=True,
            block_reason="Audio files must be downloaded locally before transcription.",
        )
