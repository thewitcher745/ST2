from typing import Dict, Optional, List, Union
from numpy.lib.stride_tricks import sliding_window_view
from pandas import DataFrame
import numpy as np


class MSBIdentifier:
    def __init__(self):
        """
        Initializes 3-pivot patterns for Market Structure Breaks (MSB).
        A break is defined by the transition from a trend-continuation
        pivot to a trend-reversal pivot.
        """
        # Bullish MSB: Transition from LH to HH
        self.bullish_patterns = [("LH", "LL", "HH"), ("LH", "HL", "HH")]

        # Bearish MSB: Transition from HL to LL
        self.bearish_patterns = [("HL", "HH", "LL"), ("HL", "LH", "LL")]

    def _match_sequence(
        self, sequence: np.ndarray
    ) -> Optional[Dict[str, Union[str, int]]]:
        """Matches a 3-pivot window against MSB definitions."""
        seq_tuple = tuple(sequence)

        if seq_tuple in self.bullish_patterns:
            return {"direction": "bullish"}

        if seq_tuple in self.bearish_patterns:
            return {"direction": "bearish"}

        return None

    def find_all_matches(
        self, structure_list: List[str], klines_indices: List[int]
    ) -> DataFrame:
        """
        Scans for 3-pivot MSB patterns and anchors them to the START of the pattern.
        """
        if len(structure_list) < 3:
            return DataFrame(columns=["direction", "pivot_index", "kline_index"])

        tags = np.array(structure_list)
        k_idx = np.array(klines_indices)

        # 1. Create 3-pivot sliding windows
        # We start from the beginning of tags. window[0] = tags[0, 1, 2]
        windows = sliding_window_view(tags, 3)

        # 2. Map the matches
        matches = [self._match_sequence(w) for w in windows]

        # 3. Filter and build results
        results = []
        for i, match in enumerate(matches):
            if match:
                # Can't have two same direction MSB's, so skip if the last one has the same
                # direction
                if results and results[-1]["direction"] == match["direction"]:
                    continue

                start_pivot_idx = i

                result_entry = match.copy()
                result_entry["pivot_index"] = start_pivot_idx
                result_entry["kline_index"] = k_idx[start_pivot_idx]

                results.append(result_entry)

        return (
            DataFrame(results)
            if results
            else DataFrame(columns=["direction", "pivot_index", "kline_index"])
        )
