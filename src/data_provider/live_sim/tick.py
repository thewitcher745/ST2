from dataclasses import dataclass

from pandas import Timestamp


@dataclass(frozen=True)
class Tick:
    timestamp: Timestamp
    price: float
    candle_index: int
