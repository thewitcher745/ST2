"""
This module contains a singleton definition to avoid multiple injections of dependencies.
It also defines the klines_df dataframe column as numpy arrays for fast access.
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
