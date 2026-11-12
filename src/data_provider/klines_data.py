"""
This module defines the klines_df dataframe column as numpy arrays for fast access.
"""

from numpy import array, float64, isfinite
from numpy.typing import NDArray
from pandas import DataFrame


class KLinesData:
    def __init__(self, klines_df: DataFrame):
        self.time: NDArray = array(klines_df.time, dtype=object)
        self.open: NDArray[float64] = array(klines_df.open)
        self.high: NDArray[float64] = array(klines_df.high)
        self.low: NDArray[float64] = array(klines_df.low)
        self.close: NDArray[float64] = array(klines_df.close)
        self.length = len(self.close)

    def calculate_atr_before(self, base_candle_index: int) -> float | None:
        """Mean high-low range of the 14 candles strictly before the base candle.

        This strategy uses individual candle ranges, without gap adjustments or
        Wilder smoothing. Incomplete, invalid, or zero-range history is unavailable.
        """
        if not 14 <= base_candle_index < self.length:
            return None

        ranges = (
            self.high[base_candle_index - 14 : base_candle_index]
            - self.low[base_candle_index - 14 : base_candle_index]
        )
        if not isfinite(ranges).all() or (ranges < 0).any():
            return None
        atr = float(ranges.mean())
        return atr if isfinite(atr) and atr > 0 else None

    def get_dict_format(self):
        return {
            "time": self.time.astype("datetime64[ns]").astype("int64"),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
        }
