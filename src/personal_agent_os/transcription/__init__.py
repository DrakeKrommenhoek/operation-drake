from personal_agent_os.config import get_settings
from personal_agent_os.transcription.base import TranscriptionProvider


def get_transcription_provider() -> TranscriptionProvider:
    name = get_settings().default_transcription_provider
    if name == "openai_whisper":
        from personal_agent_os.transcription.openai_whisper import OpenAIWhisperTranscriber
        return OpenAIWhisperTranscriber()
    from personal_agent_os.transcription.mock_transcriber import MockTranscriber
    return MockTranscriber()
