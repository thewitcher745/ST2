from abc import ABC, abstractmethod
from typing import AsyncGenerator

from .tick import Tick


class AbstractTickProvider(ABC):
    @abstractmethod
    def ticks(self) -> AsyncGenerator[Tick, None]:
        pass

    def set_symbols(self, symbols: list[str]):
        self._symbols = symbols
