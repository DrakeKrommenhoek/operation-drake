from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ContentResult:
    url: str
    title: str = ""
    text: str = ""
    error: str = ""
    blocked: bool = False
    block_reason: str = ""


class ContentAdapter(ABC):
    @abstractmethod
    def can_handle(self, url: str) -> bool: ...

    @abstractmethod
    def extract(self, url: str) -> ContentResult: ...
