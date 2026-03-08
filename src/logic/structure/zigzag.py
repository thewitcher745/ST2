from pandas import DataFrame
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

class Zigzag:
    def __init__(self, window_size: int = 9):
        self.window_size = window_size

    def calculate(self, klines_df: DataFrame) -> DataFrame:
        n = len(klines_df)
        if n < self.window_size:
            return DataFrame(columns=["kline_index", "time", "pivot_value", "pivot_type", "pivot_formation_index"])

        # Vectorized extraction
        highs = klines_df["high"].to_numpy()
        lows = klines_df["low"].to_numpy()
        closes = klines_df["close"].to_numpy()
        opens = klines_df["open"].to_numpy()
        times = klines_df["time"].to_numpy()

        # 1. Vectorized Extremes
        # Sliding window looks at the previous window_size elements
        win_highs = sliding_window_view(highs, self.window_size)
        win_lows = sliding_window_view(lows, self.window_size)

        is_peak_array = np.zeros(n, dtype=bool)
        is_valley_array = np.zeros(n, dtype=bool)

        # A candle is a pivot if its extreme is greater/less than the window EXCLUDING itself
        is_peak_array[self.window_size-1:] = highs[self.window_size-1:] > np.max(win_highs[:, :-1], axis=1)
        is_valley_array[self.window_size-1:] = lows[self.window_size-1:] < np.min(win_lows[:, :-1], axis=1)

        pivots = []
        last_type = 0  # 1: Peak, -1: Valley

        def update_pivot(idx, time, val, p_type):
            nonlocal last_type
            if last_type == p_type:
                # Extension logic: only update if the new value is more extreme
                if (p_type == 1 and val > pivots[-1]["pivot_value"]) or \
                   (p_type == -1 and val < pivots[-1]["pivot_value"]):
                    pivots[-1] = self._make_dict(idx, time, val, p_type, idx)
            else:
                # New leg logic: current candle confirms the previous pivot's completion
                if pivots:
                    pivots[-1]["pivot_formation_index"] = idx
                
                pivots.append(self._make_dict(idx, time, val, p_type, idx))
                last_type = p_type

        # 2. Sequential Logic Pass
        for i in range(self.window_size - 1, n):
            peak = is_peak_array[i]
            valley = is_valley_array[i]

            if peak and valley:
                # Intraday order approximation via candle color
                if closes[i] < opens[i]: # Red: High then Low
                    update_pivot(i, times[i], highs[i], 1)
                    update_pivot(i, times[i], lows[i], -1)
                else: # Green: Low then High
                    update_pivot(i, times[i], lows[i], -1)
                    update_pivot(i, times[i], highs[i], 1)
            elif peak:
                update_pivot(i, times[i], highs[i], 1)
            elif valley:
                update_pivot(i, times[i], lows[i], -1)

        if not pivots:
            return DataFrame(columns=["kline_index", "time", "pivot_value", "pivot_type", "pivot_formation_index"])

        # The last leg is only formed "virtually", meaning that even though a candle has virtually confirmed the
        # second-to-last pivot, it itself isn't confirmed as a pivot until later, when a pivot of the opposite
        # direction is seen. Therefore the very last pivot found should not be considered confimed.
        zigzag_df = DataFrame(pivots[:-1])

        # 3. Market Structure Labeling (HH, LH, LL, HL)
        vals = zigzag_df["pivot_value"].to_numpy()
        typs = zigzag_df["pivot_type"].to_numpy()
        structure = np.full(len(zigzag_df), "", dtype="U2")

        for i in range(2, len(zigzag_df)):
            if typs[i] == 1: # Peak
                structure[i] = "HH" if vals[i] > vals[i-2] else "LH"
            else: # Valley
                structure[i] = "LL" if vals[i] < vals[i-2] else "HL"

        zigzag_df["structure"] = structure
        return zigzag_df

    @staticmethod
    def _make_dict(idx, time, val, p_type, f_idx):
        return {
            "kline_index": idx,
            "time": time,
            "pivot_value": val,
            "pivot_type": p_type,
            "pivot_formation_index": f_idx
        }