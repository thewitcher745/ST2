from abc import ABC, abstractmethod
from typing import Iterator
from .tick import Tick


class AbstractTickProvider(ABC):
    @property
    @abstractmethod
    def tick_interval(self) -> float: ...

    @abstractmethod
    def ticks(self) -> Iterator[Tick]: ...
