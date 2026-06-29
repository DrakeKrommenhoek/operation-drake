from openai import OpenAI

from operation_drake.config import get_settings
from operation_drake.transcription.base import TranscriptionProvider


class OpenAIWhisperTranscriber(TranscriptionProvider):
    provider_name = "openai_whisper"

    def __init__(self):
        key = get_settings().openai_whisper_api_key or get_settings().openai_api_key
        self._client = OpenAI(api_key=key)

    def transcribe(self, audio_path: str) -> str:
        with open(audio_path, "rb") as f:
            result = self._client.audio.transcriptions.create(model="whisper-1", file=f)
        return result.text
