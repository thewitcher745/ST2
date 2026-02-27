from pandas import DataFrame
import numpy as np


class Zigzag:
    def __init__(self, window_size: int = 9):
        """
        Initializes the Zigzag indicator.

        Args:
            window_size: The number of periods to look back for determining local extrema.
        """
        self.window_size = window_size

    def calculate(self, klines_df: DataFrame) -> DataFrame:
        """
        Calculates the Zigzag indicator for the given data. A zigzag point forms at a candle whose
        high or low is higher than all of the highs in the previous window_size candles or lower than
        all of the lows in the previous window_size candles. If the last zigzag point was a peak and
        the last one is a valley, a new leg is formed, and vice versa. If the types of the zigzag points
        are the same, the same leg is extended.

        Args:
            klines_df: The data to calculate the Zigzag indicator for.

        Returns:
            DataFrame: A DataFrame with the Zigzag indicator. It has 4 columns:
                - klines_df_index: The index of the point in the original data
                - time: The timestamp of the point
                - pivot_value: The pivot value at that point
                - pivot_type: The type of the pivot point (1 for peak, -1 for valley)
        """
        n = len(klines_df)
        if n < self.window_size:
            return DataFrame(
                columns=["kline_index", "time", "pivot_value", "pivot_type"]
            )

        # Convert columns to NumPy arrays for raw memory speed
        highs = klines_df["high"].to_numpy()
        lows = klines_df["low"].to_numpy()
        closes = klines_df["close"].to_numpy()
        opens = klines_df["open"].to_numpy()
        times = klines_df["time"].to_numpy()

        # 1. Vectorized calculation of local extremes
        # We find the rolling max/min for every index in one go using sliding_window_view
        from numpy.lib.stride_tricks import sliding_window_view

        # padding the start to keep array lengths equal to n
        win_highs = sliding_window_view(highs, self.window_size)
        win_lows = sliding_window_view(lows, self.window_size)

        # Calculate local max/min for each window
        # We offset indices by (window_size - 1) because sliding_window starts at index window_size-1
        is_peak_array = np.zeros(n, dtype=bool)
        is_valley_array = np.zeros(n, dtype=bool)

        # A candle is a peak if it's the max of its own lookback window
        is_peak_array[self.window_size - 1 :] = highs[self.window_size - 1 :] > np.max(
            win_highs[:, :-1], axis=1
        )
        is_valley_array[self.window_size - 1 :] = lows[self.window_size - 1 :] < np.min(
            win_lows[:, :-1], axis=1
        )

        # 2. Linear pass to handle leg logic (Extension vs New Leg)
        # We pre-allocate lists or arrays; lists are actually very fast for appending dictionaries
        pivots = []
        last_type = 0  # 0: None, 1: Peak, -1: Valley

        for i in range(self.window_size - 1, n):
            # If the candle registers both a valley and a peak, change the direction and register a pivot.
            if is_peak_array[i] and is_valley_array[i]:
                is_red = closes[i] < opens[i]

                if is_red:
                    # Logic: Hit Peak first, then Valley.
                    # 1. Did the Peak part of this candle extend the previous High leg?
                    if last_type == 1 and highs[i] > pivots[-1]["pivot_value"]:
                        pivots[-1] = self._make_dict(i, times[i], highs[i], 1)

                    # 2. Now register the reversal to the Valley (the "later" data)
                    if last_type != -1:
                        pivots.append(self._make_dict(i, times[i], lows[i], -1))
                        last_type = -1
                    else:
                        # If we were already in a valley, just extend it
                        if lows[i] < pivots[-1]["pivot_value"]:
                            pivots[-1] = self._make_dict(i, times[i], lows[i], -1)

            elif is_peak_array[i]:
                val = highs[i]
                if last_type == 1:
                    # Extend the previous leg only if the current pivot has a higher value
                    if val > pivots[-1]["pivot_value"]:
                        pivots[-1] = self._make_dict(i, times[i], val, 1)
                else:
                    # New Leg
                    pivots.append(self._make_dict(i, times[i], val, 1))
                    last_type = 1

            elif is_valley_array[i]:
                val = lows[i]
                if last_type == -1:
                    # Extend the previous leg only if the current pivot has a lower value
                    if val < pivots[-1]["pivot_value"]:
                        pivots[-1] = self._make_dict(i, times[i], val, -1)
                else:
                    # New Leg
                    pivots.append(self._make_dict(i, times[i], val, -1))
                    last_type = -1

        zigzag_df = DataFrame(pivots)

        # 3. Detect lower lows, lower highs, lower highs and higher highs
        values = zigzag_df["pivot_value"].to_numpy()
        types = zigzag_df["pivot_type"].to_numpy()

        # Initialize an array of empty strings (shorter strings = less memory)
        structure = np.full(len(zigzag_df), "", dtype="U2")

        # We start from the 3rd pivot because we need a previous pivot of the same type to compare
        for i in range(2, len(zigzag_df)):
            current_val = values[i]
            prev_same_type_val = values[i - 2]

            if types[i] == 1:  # Current is a PEAK
                structure[i] = "HH" if current_val > prev_same_type_val else "LH"
            else:  # Current is a VALLEY
                structure[i] = "LL" if current_val < prev_same_type_val else "HL"

        zigzag_df["structure"] = structure

        return zigzag_df

    @staticmethod
    def _make_dict(idx, time, val, p_type):
        return {
            "kline_index": idx,
            "time": time,
            "pivot_value": val,
            "pivot_type": p_type,
        }
