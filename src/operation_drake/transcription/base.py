from abc import ABC, abstractmethod


class TranscriptionProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> str: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...
