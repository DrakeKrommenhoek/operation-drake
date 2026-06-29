from operation_drake.config import get_settings
from operation_drake.transcription.base import TranscriptionProvider

_VALID = ("openai_whisper", "mock")


def get_transcription_provider() -> TranscriptionProvider:
    name = get_settings().default_transcription_provider
    if name == "openai_whisper":
        from operation_drake.transcription.openai_whisper import OpenAIWhisperTranscriber

        return OpenAIWhisperTranscriber()
    if name == "mock":
        from operation_drake.transcription.mock_transcriber import MockTranscriber

        return MockTranscriber()
    raise ValueError(
        f"Unknown DEFAULT_TRANSCRIPTION_PROVIDER '{name}'. Valid values: {', '.join(_VALID)}"
    )
