from numpy.lib.stride_tricks import sliding_window_view
from pandas import DataFrame
from numpy import array

from src.config import Config

config = Config()


class MSBIdentifier:
    def __init__(self, fib_factor: float = config.fib_factor):
        """
        Initializes 3-pivot patterns for Market Structure Breaks (MSB).
        A break is defined by the transition from a trend-continuation
        pivot to a trend-reversal pivot.

        Args:
            fib_factor (float): The ratio which the leg breaking a potential swing high or swing low
            must exceed in order to confirm an MSB
        """
        self.fib_factor = fib_factor

    def find_all_matches(
        self,
        pivot_types: list,
        klines_indices: list,
        pivot_values: list,
        pivot_formation_indices: list,
    ) -> DataFrame:
        """
        Scans for 4-pivot patterns where Pivot 1 is the MSB level.

        Leg Before: Pivot 0 -> Pivot 1
        Leg After:  Pivot 1 -> Pivot 2
        Confirmation: Pivot 3 breaks Pivot 1
        """
        if len(pivot_types) < 4:
            return DataFrame(
                columns=[
                    "direction",
                    "formation_index",
                    "pivot_index",
                    "kline_index",
                    "break_level",
                    "leg_before",
                    "leg_after",
                ]
            )

        types = array(pivot_types)
        k_idx = array(klines_indices)
        prices = array(pivot_values)

        # 1. Create 4-pivot windows
        type_windows = sliding_window_view(types, 4)
        price_windows = sliding_window_view(prices, 4)

        results = []
        for i, (types_win, prices_win) in enumerate(zip(type_windows, price_windows)):
            # We match based on the pivot types and the direct price relationship
            # between the broken pivot (p1) and the breaking pivot (p3).
            _, p1, p2, p3 = prices_win
            t0, t1, t2, t3 = types_win

            direction = None
            if t0 == -1 and t1 == 1 and t2 == -1 and t3 == 1 and p3 > p1:
                direction = "bullish"
            elif t0 == 1 and t1 == -1 and t2 == 1 and t3 == -1 and p3 < p1:
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
                    # pivot_formation_indices[i + 3] comes from the fact that i is the first leg in the 4-leg arrangment
                    # of legs that forms the MSB confirmation. i + 1 is the leg from the MSB to the valley after it. i + 2 is
                    # the move that breaks the swing high or swing low. i + 3 is the movement that forms the final pivot and
                    # the 3rd leg of the move.
                    results.append(
                        {
                            "direction": direction,
                            "formation_index": pivot_formation_indices[i + 3],
                            "pivot_index": i + 1,  # Anchored to the broken pivot
                            "kline_index": int(k_idx[i + 1]),
                            "break_level": p1,
                            # The two consecutive legs joining at the MSB (p1)
                            "leg_before": (int(k_idx[i]), int(k_idx[i + 1]) + 1),
                            "leg_after": (int(k_idx[i + 1]), int(k_idx[i + 2]) + 1),
                        }
                    )

        return (
            DataFrame(results)
            if results
            else DataFrame(
                columns=[
                    "direction",
                    "formation_index",
                    "pivot_index",
                    "kline_index",
                    "break_level",
                    "leg_before",
                    "leg_after",
                ]
            )
        )
