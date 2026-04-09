from numpy import append, array
from pandas import DataFrame, Timestamp

from .klines_data import KLinesData
from .live.tick import Tick


class LiveKLinesData(KLinesData):
    def update(self, tick: Tick):
        """
        Takes a tick as input, which is just a candle, and updates the latest candle with it.
        """
        self.close[-1] = tick.close
        self.high[-1] = tick.high
        self.low[-1] = tick.low
        self.open[-1] = tick.open

    def replace(self, klines_df: DataFrame, partial=False):
        """
        Replaces the data with new data completely (or just the most recent n candles, if the partial flag is set to True)
        Performed when there is a data gap or mismatch.
        """
        if partial:
            incoming_length = len(klines_df)
            self.time[-incoming_length:] = array(klines_df.time, dtype=object)

            self.open[-incoming_length:] = array(klines_df.open)
            self.high[-incoming_length:] = array(klines_df.high)
            self.low[-incoming_length:] = array(klines_df.low)
            self.close[-incoming_length:] = array(klines_df.close)
            # The length doesn't change in a partial replacement so it isn't recalculated.

            return

        self.time = array(klines_df.time, dtype=object)
        self.open = array(klines_df.open)
        self.high = array(klines_df.high)
        self.low = array(klines_df.low)
        self.close = array(klines_df.close)
        self.length = len(self.close)

    @property
    def live_candle_time(self) -> Timestamp:
        """
        The time of the last live candle
        """
        t = self.time[-1]
        assert isinstance(t, Timestamp)
        return t

    @property
    def last_closed_time(self) -> Timestamp:
        """
        The time of the last closed candle
        """
        t = self.time[-2]
        assert isinstance(t, Timestamp)
        return t
