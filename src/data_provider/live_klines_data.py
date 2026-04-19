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
            incoming_first_time = klines_df.time.iloc[0]

            # Find the index where the incoming data should start replacing
            matches = self.time == incoming_first_time
            indices = matches.nonzero()[0]

            if len(indices) > 0:
                start_idx = indices[0]
            else:
                # Fallback to length-based replacement
                incoming_length = len(klines_df)
                start_idx = len(self.time) - incoming_length

            # Replace from start_idx to end, then append the extra candle
            candles_to_replace = len(self.time) - start_idx

            # Replace the overlapping portion
            self.time[start_idx:] = array(
                klines_df.time[:candles_to_replace], dtype=object
            )
            self.open[start_idx:] = array(klines_df.open[:candles_to_replace])
            self.high[start_idx:] = array(klines_df.high[:candles_to_replace])
            self.low[start_idx:] = array(klines_df.low[:candles_to_replace])
            self.close[start_idx:] = array(klines_df.close[:candles_to_replace])

            # Append the new candle (the extra one)
            if len(klines_df) > candles_to_replace:
                self.time = append(self.time, klines_df.time.iloc[-1])
                self.open = append(self.open, klines_df.open.iloc[-1])
                self.high = append(self.high, klines_df.high.iloc[-1])
                self.low = append(self.low, klines_df.low.iloc[-1])
                self.close = append(self.close, klines_df.close.iloc[-1])
                self.length = len(self.close)

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
