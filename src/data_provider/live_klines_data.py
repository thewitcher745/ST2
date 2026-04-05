"""
This module contains a singleton definition to avoid multiple injections of dependencies.
It also defines the klines_df dataframe column as numpy arrays for fast access.
"""

from numpy import append, array

from .klines_data import KLinesData
from .live.tick import Tick


class LiveKLinesData(KLinesData):
    def update(self, tick: Tick):
        if self.time[-1] == tick.timestamp:
            self.close[-1] = tick.close
            self.high[-1] = tick.high
            self.low[-1] = tick.low
            self.open[-1] = tick.open
        else:
            self.time = append(self.time, array(tick.timestamp, dtype=object))
            self.open = append(self.open, tick.open)
            self.high = append(self.high, tick.high)
            self.low = append(self.low, tick.low)
            self.close = append(self.close, tick.close)
            self.length += 1
