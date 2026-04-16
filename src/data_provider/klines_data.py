"""
This module defines the klines_df dataframe column as numpy arrays for fast access.
"""

from numpy import array, float64
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

    def get_dict_format(self):
        return {
            "time": self.time.astype("datetime64[ns]").astype("int64"),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
        }
