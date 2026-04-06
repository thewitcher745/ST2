from dataclasses import dataclass
from pandas import Timestamp


@dataclass(frozen=True)
class Tick:
    symbol: str
    event_time: Timestamp
    price: float
    open: float
    high: float
    low: float
    close: float
    timestamp: Timestamp
