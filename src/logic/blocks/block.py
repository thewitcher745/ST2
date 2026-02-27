from abc import ABC
from typing import Any, Dict
from pandas import Timestamp


class Block(ABC):
    """
    Abstract Base Class for blocks.
    """

    def __init__(
        self,
        base_candle_index: int,
        base_candle_time: Timestamp,
        direction: str,
        block_type: str,
        low: float,
        high: float,
        start_time: Timestamp,
    ):

        self.base_candle_index = base_candle_index
        self.base_candle_time = base_candle_time
        self.direction = direction  # 'long' or 'short'
        self.block_type = block_type  # 'OB', 'BB', or 'MB'
        self.low = low
        self.high = high
        self.start_time = start_time
        self.end_time = None

        self.id = f"{'Bu' if self.direction == 'bullish' else 'Be'}_{self.block_type}_{base_candle_time.strftime('%Y-%m-%dT%H:%M:%S')}"

    def to_dict(self) -> Dict[str, Any]:
        """Utility for converting to a DataFrame-ready format."""
        return {
            "id": self.id,
            "type": self.block_type,
            "direction": self.direction,
            "low": self.low,
            "high": self.high,
            "start_time": self.start_time,
            "base_candle_index": self.base_candle_index,
            "end_time": self.end_time,
        }
