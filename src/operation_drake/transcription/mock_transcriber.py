from operation_drake.transcription.base import TranscriptionProvider


class MockTranscriber(TranscriptionProvider):
    provider_name = "mock"

    def transcribe(self, audio_path: str) -> str:
        return f"[Mock transcription of {audio_path}] This is a simulated voice note transcription for testing purposes."
