from abc import ABC
from typing import Any, Dict
from pandas import DataFrame, Timestamp
import numpy as np


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
        invalidation_price: float,
    ):
        self.base_candle_index = base_candle_index
        self.base_candle_time = base_candle_time
        self.direction = direction  # 'bullish' or 'bearish'
        self.block_type = block_type  # 'OB', 'BB', or 'MB'
        self.low = low
        self.high = high
        self.start_time = start_time
        self.end_time = None
        self.end_index = None
        self.invalidation_price = invalidation_price

        self.id = f"{'Bu' if self.direction == 'bullish' else 'Be'}_{self.block_type}_{base_candle_time.strftime('%Y-%m-%dT%H:%M:%S')}"

    def check_end_candle(self, klines_df: DataFrame):
        """
        This method checks if the price has closed below/above the invalidation price.
        """
        closes_after_start: np.array = klines_df.iloc[self.base_candle_index :].close

        if self.direction == "bullish":
            invalidating_candles = np.where(
                closes_after_start < self.invalidation_price
            )[0]
            if len(invalidating_candles):
                return invalidating_candles[0] + self.base_candle_index

        else:
            invalidating_candles = np.where(
                closes_after_start > self.invalidation_price
            )[0]
            if len(invalidating_candles):
                return invalidating_candles[0] + self.base_candle_index

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
            "base_candle_time": self.base_candle_time,
            "end_time": self.end_time,
        }
