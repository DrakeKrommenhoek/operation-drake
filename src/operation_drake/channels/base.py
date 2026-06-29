from abc import ABC, abstractmethod


class ChannelAdapter(ABC):
    @abstractmethod
    def send(self, text: str, reply_to: str | None = None) -> None: ...

    @property
    @abstractmethod
    def channel_name(self) -> str: ...
