from __future__ import annotations
from abc import ABC
from typing import TYPE_CHECKING, Any, Dict, Literal, Optional
from pandas import Timestamp
from numpy.typing import NDArray
from numpy import where

if TYPE_CHECKING:
    from src.logic import Position


class Block(ABC):
    """
    Abstract Base Class for blocks.
    """

    def __init__(
        self,
        base_candle_index: int,
        base_candle_time: Timestamp,
        msb_kline_index: int,
        direction: Literal["bullish", "bearish"],
        block_type: Literal["BB", "MB", "OB"],
        low: float,
        high: float,
        start_index: int,
        start_time: Timestamp,
        invalidation_price: float,
    ):
        self.base_candle_index: int = base_candle_index
        self.base_candle_time: Timestamp = base_candle_time
        self.msb_kline_index: int = msb_kline_index
        self.direction: Literal["bullish", "bearish"] = (
            direction  # 'bullish' or 'bearish'
        )
        self.block_type: Literal["BB", "MB", "OB"] = block_type  # 'OB', 'BB', or 'MB'
        self.low: float = low
        self.high: float = high
        self.height: float = high - low
        self.height_percentage: float = (high - low) / ((high + low) / 2) * 100
        self.start_index: int = start_index
        self.start_time: Timestamp = start_time
        self.end_time: Optional[Timestamp] = None
        self.end_index: Optional[int] = None
        self.invalidation_price: float = invalidation_price

        # The positions associated with (derived from) the block
        self.positions: list[Position] = []

        self.id = f"{'Bu' if self.direction == 'bullish' else 'Be'}_{self.block_type}_{base_candle_time.strftime('%Y-%m-%dT%H:%M:%S')}"

    def __eq__(self, other) -> bool:
        return self.id == other.id

    def check_end_candle(self, klines_df_close_array: NDArray):
        """
        This method checks if the price has closed below/above the invalidation price.
        """
        closes_after_start = klines_df_close_array[self.base_candle_index :]

        if self.direction == "bullish":
            invalidating_candles = where(closes_after_start < self.invalidation_price)[
                0
            ]
            if len(invalidating_candles):
                return invalidating_candles[0] + self.base_candle_index

        else:
            invalidating_candles = where(closes_after_start > self.invalidation_price)[
                0
            ]
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

    def __repr__(self):
        return self.id
