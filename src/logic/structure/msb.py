from typing import Dict, Optional, List, Union
from numpy.lib.stride_tricks import sliding_window_view
from pandas import DataFrame
import numpy as np


class MSBIdentifier:
    def __init__(self, fib_factor: float = 0.33):
        """
        Initializes 3-pivot patterns for Market Structure Breaks (MSB).
        A break is defined by the transition from a trend-continuation
        pivot to a trend-reversal pivot.

        Args:
            fib_factor (float): The ratio which the leg breaking a potential swing high or swing low
            must exceed in order to confirm an MSB
        """
        self.fib_factor = fib_factor

        # Bullish MSB: Transition from LH to HH
        self.bullish_patterns = [("LH", "LL", "HH"), ("LH", "HL", "HH")]

        # Bearish MSB: Transition from HL to LL
        self.bearish_patterns = [("HL", "HH", "LL"), ("HL", "LH", "LL")]

    def _match_sequence(
        self, sequence: np.ndarray
    ) -> Optional[Dict[str, Union[str, int, tuple]]]:
        """Matches a 3-pivot window against MSB definitions."""
        seq_tuple = tuple(sequence)

        if seq_tuple in self.bullish_patterns:
            return {"direction": "bullish"}

        if seq_tuple in self.bearish_patterns:
            return {"direction": "bearish"}

        return None

    def find_all_matches(
        self, structure_list: list, klines_indices: list, pivot_values: list
    ) -> DataFrame:
        """
        Scans for 4-pivot patterns where Pivot 1 is the MSB level.

        Leg Before: Pivot 0 -> Pivot 1
        Leg After:  Pivot 1 -> Pivot 2
        Confirmation: Pivot 3 breaks Pivot 1
        """
        if len(structure_list) < 4:
            return DataFrame(
                columns=[
                    "direction",
                    "pivot_index",
                    "kline_index",
                    "break_level",
                    "leg_before",
                    "leg_after",
                ]
            )

        tags = np.array(structure_list)
        k_idx = np.array(klines_indices)
        prices = np.array(pivot_values)

        # 1. Create 4-pivot windows
        tag_windows = sliding_window_view(tags, 4)
        price_windows = sliding_window_view(prices, 4)

        results = []
        for i, (tags_win, prices_win) in enumerate(zip(tag_windows, price_windows)):
            # We match based on the 'broken' pivot (index 1) and 'breaking' pivot (index 3)
            # Bullish: Pivot 1 was a LH, Pivot 3 is a HH
            # Bearish: Pivot 1 was a HL, Pivot 3 is a LL

            p0, p1, p2, p3 = prices_win
            t1, t3 = tags_win[1], tags_win[3]

            direction = None
            if t1 == "LH" and t3 == "HH":
                direction = "bullish"
            elif t1 == "HL" and t3 == "LL":
                direction = "bearish"

            if direction:
                # Fib confirmation: Does P3 break P1 significantly relative to the P1-P2 leg?
                leg_range = abs(p1 - p2)
                threshold = leg_range * self.fib_factor

                confirmed = False
                if direction == "bullish" and p3 > (p1 + threshold):
                    confirmed = True
                elif direction == "bearish" and p3 < (p1 - threshold):
                    confirmed = True

                if confirmed:
                    # Prevent consecutive MSBs in the same direction
                    if results and results[-1]["direction"] == direction:
                        continue

                    results.append(
                        {
                            "direction": direction,
                            "pivot_index": i + 1,  # Anchored to the broken pivot
                            "kline_index": int(k_idx[i + 1]),
                            "break_level": p1,
                            # The two consecutive legs joining at the MSB (p1)
                            "leg_before": (int(k_idx[i]), int(k_idx[i + 1])),
                            "leg_after": (int(k_idx[i + 1]), int(k_idx[i + 2])),
                        }
                    )

        return (
            DataFrame(results)
            if results
            else DataFrame(
                columns=[
                    "direction",
                    "pivot_index",
                    "kline_index",
                    "break_level",
                    "leg_before",
                    "leg_after",
                ]
            )
        )
