from pandas import DataFrame
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


class Zigzag:
    def __init__(self, window_size: int = 9):
        self.window_size = window_size

    def calculate(self, klines_df: DataFrame) -> DataFrame:
        n = len(klines_df)
        if n < self.window_size:
            return DataFrame(
                columns=[
                    "kline_index",
                    "time",
                    "pivot_value",
                    "pivot_type",
                    "pivot_formation_index",
                ]
            )

        highs = klines_df["high"].to_numpy()
        lows = klines_df["low"].to_numpy()
        closes = klines_df["close"].to_numpy()
        opens = klines_df["open"].to_numpy()
        times = klines_df["time"].to_numpy()

        # 1. Vectorized calculation of local extremes
        # We look at the window ending at i-1 to see if kline i breaks the window
        win_highs = sliding_window_view(highs, self.window_size)
        win_lows = sliding_window_view(lows, self.window_size)

        is_peak_array = np.zeros(n, dtype=bool)
        is_valley_array = np.zeros(n, dtype=bool)

        # A candle is a peak if it's the max of its own lookback window
        is_peak_array[self.window_size - 1 :] = highs[self.window_size - 1 :] > np.max(
            win_highs[:, :-1], axis=1
        )
        is_valley_array[self.window_size - 1 :] = lows[self.window_size - 1 :] < np.min(
            win_lows[:, :-1], axis=1
        )

        pivots = []
        last_type = 0  # 1: Peak, -1: Valley

        for i in range(self.window_size, n):
            # Case A: Candle is both a Peak and a Valley
            if is_peak_array[i] and is_valley_array[i]:
                # If candle is Red, assume High hit first, then Low
                if closes[i] < opens[i]:
                    order = [(highs[i], 1), (lows[i], -1)]
                else:  # Green candle: Low hit first, then High
                    order = [(lows[i], -1), (highs[i], 1)]

                for val, p_type in order:
                    last_type = self._process_pivot(
                        pivots, i, times[i], val, p_type, last_type
                    )

            # Case B: Only a Peak
            elif is_peak_array[i]:
                last_type = self._process_pivot(
                    pivots, i, times[i], highs[i], 1, last_type
                )

            # Case C: Only a Valley
            elif is_valley_array[i]:
                last_type = self._process_pivot(
                    pivots, i, times[i], lows[i], -1, last_type
                )

        if not pivots:
            return DataFrame(
                columns=[
                    "kline_index",
                    "time",
                    "pivot_value",
                    "pivot_type",
                    "pivot_formation_index",
                ]
            )

        zigzag_df = DataFrame(pivots)

        # 3. Detect Market Structure (HH, LH, LL, HL)
        values = zigzag_df["pivot_value"].to_numpy()
        types = zigzag_df["pivot_type"].to_numpy()
        structure = np.full(len(zigzag_df), "", dtype="U2")

        for i in range(2, len(zigzag_df)):
            if types[i] == 1:  # Peak
                structure[i] = "HH" if values[i] > values[i - 2] else "LH"
            else:  # Valley
                structure[i] = "LL" if values[i] < values[i - 2] else "HL"

        zigzag_df["structure"] = structure
        return zigzag_df

    def _process_pivot(self, pivots, idx, time, val, p_type, last_type):
        """Handles logic for extending an existing leg or starting a new one."""
        if last_type == p_type:
            # Same type: Check for extension
            if (p_type == 1 and val > pivots[-1]["pivot_value"]) or (
                p_type == -1 and val < pivots[-1]["pivot_value"]
            ):
                pivots[-1] = self._make_dict(idx, time, val, p_type, 0)
        else:
            # Reversal: New leg
            if len(pivots) > 0:
                pivots[-1]["pivot_formation_index"] = idx
            pivots.append(self._make_dict(idx, time, val, p_type, 0))
            last_type = p_type
        return last_type

    @staticmethod
    def _make_dict(idx, time, val, p_type, p_formation_idx):
        return {
            "kline_index": idx,  # Where the price point actually is
            "time": time,  # Timestamp of the price point
            "pivot_value": val,  # High or Low value
            "pivot_type": p_type,  # 1 for Peak, -1 for Valley
            "pivot_formation_index": p_formation_idx,  # Index of the candle that confirmed it
        }
