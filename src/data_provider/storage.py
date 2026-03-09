"""
This module contains a singleton definition to avoid multiple injections of dependencies.
It also defines the klines_df dataframe column as numpy arrays for fast access.
"""

from numpy import array
from pandas import DataFrame


class KLinesData:
    def __init__(self, klines_df: DataFrame):
        self.klines_df = klines_df
        self.time = array(self.klines_df.time)
        self.open = array(self.klines_df.open)
        self.high = array(self.klines_df.high)
        self.low = array(self.klines_df.low)
        self.close = array(self.klines_df.close)
        self.length = len(self.close)
