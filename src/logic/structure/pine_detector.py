from collections import deque
from dataclasses import dataclass
from typing import Literal

import numpy as np
from pandas import DataFrame

from src.data_provider import KLinesData


@dataclass(frozen=True)
class BlockFormation:
    base_candle_index: int
    msb_kline_index: int
    direction: Literal["bullish", "bearish"]
    block_type: Literal["OB", "BB", "MB"]
    formation_index: int
    invalidation_price: float
    preformation_check_start_index: int


@dataclass
class PineDetectionResult:
    zigzag_df: DataFrame
    msbs_df: DataFrame
    formations: list[BlockFormation]


@dataclass(frozen=True)
class _Pivot:
    value: float
    index: int
    position: int


class _ExtremeWindow:
    def __init__(self, highest: bool):
        self.highest = highest
        self.values: deque[tuple[int, float]] = deque()

    def update(self, index: int, value: float, start: int) -> float:
        while self.values and self.values[0][0] < start:
            self.values.popleft()
        while self.values:
            previous = self.values[-1][1]
            if (self.highest and previous > value) or (
                not self.highest and previous < value
            ):
                break
            self.values.pop()
        self.values.append((index, value))
        return self.values[0][1]


class PineBlockDetector:
    """Replay indicator.pine through box creation, with no box lifecycle rules."""

    PIVOT_COLUMNS = [
        "kline_index",
        "time",
        "pivot_value",
        "pivot_type",
        "pivot_formation_index",
        "structure",
    ]
    MSB_COLUMNS = [
        "direction",
        "formation_index",
        "pivot_index",
        "kline_index",
        "break_level",
        "leg_before",
        "leg_after",
    ]

    def __init__(self, zigzag_len: int, fib_factor: float):
        if zigzag_len < 1:
            raise ValueError("lag must be at least 1 for pine_replay.")
        if not 0 <= fib_factor <= 1:
            raise ValueError("fib_factor must be between 0 and 1 for pine_replay.")
        self.zigzag_len = zigzag_len
        self.fib_factor = fib_factor

    @staticmethod
    def _select_candle(
        matches: np.ndarray,
        start: int | None,
        end: int | None,
        previous: int,
    ) -> int:
        if start is None or end is None:
            return previous
        lower, upper = sorted((start, end))
        first = int(np.searchsorted(matches, lower, side="left"))
        after_last = int(np.searchsorted(matches, upper, side="right"))
        if first == after_last:
            return previous
        return int(matches[after_last - 1] if start <= end else matches[first])

    def calculate(self, klines_data: KLinesData) -> PineDetectionResult:
        high_points: list[_Pivot | None] = [None] * 5
        low_points: list[_Pivot | None] = [None] * 5
        high_index_history: list[int | None] = []
        low_index_history: list[int | None] = []
        pivots = []
        msbs = []
        formations = []
        red_candles = np.flatnonzero(klines_data.open > klines_data.close)
        green_candles = np.flatnonzero(klines_data.open < klines_data.close)
        rolling_high = _ExtremeWindow(highest=True)
        rolling_low = _ExtremeWindow(highest=False)
        pivot_high = _ExtremeWindow(highest=True)
        pivot_low = _ExtremeWindow(highest=False)
        trend = 1
        market = 1
        previous_market_input = None
        last_low_at_market_change = None
        last_high_at_market_change = None
        previous_to_up = False
        previous_to_down = False
        last_shifted_up = None
        last_shifted_down = None
        low_index = None
        high_index = None
        bullish_ob_index = 0
        bearish_ob_index = 0
        bearish_bb_index = 0
        bullish_bb_index = 0

        for bar_index in range(klines_data.length):
            high = float(klines_data.high[bar_index])
            low = float(klines_data.low[bar_index])
            window_start = max(0, bar_index - self.zigzag_len + 1)
            to_up = high >= rolling_high.update(bar_index, high, window_start)
            to_down = low <= rolling_low.update(bar_index, low, window_start)
            previous_trend = trend
            if trend == 1 and to_down:
                trend = -1
            elif trend == -1 and to_up:
                trend = 1

            if previous_to_up:
                last_shifted_up = bar_index
            if previous_to_down:
                last_shifted_down = bar_index
            low_length = (
                max(1, bar_index - last_shifted_up)
                if last_shifted_up is not None
                else 1
            )
            high_length = (
                max(1, bar_index - last_shifted_down)
                if last_shifted_down is not None
                else 1
            )
            low_value = pivot_low.update(bar_index, low, bar_index - low_length + 1)
            high_value = pivot_high.update(
                bar_index, high, bar_index - high_length + 1
            )
            if low_value == low:
                low_index = bar_index
            if high_value == high:
                high_index = bar_index
            previous_to_up = to_up
            previous_to_down = to_down

            if bar_index > 0 and trend != previous_trend:
                points = low_points if trend == 1 else high_points
                value = low_value if trend == 1 else high_value
                index = low_index if trend == 1 else high_index
                previous_pivot = points[-1]
                structure = ""
                if previous_pivot is not None:
                    if trend == 1:
                        structure = "LL" if value < previous_pivot.value else "HL"
                    else:
                        structure = "HH" if value > previous_pivot.value else "LH"
                pivot = _Pivot(value, index, len(pivots))
                points.append(pivot)
                pivots.append(
                    {
                        "kline_index": index,
                        "time": klines_data.time[index],
                        "pivot_value": value,
                        "pivot_type": -trend,
                        "pivot_formation_index": bar_index,
                        "structure": structure,
                    }
                )

            high_current, high_previous = high_points[-1], high_points[-2]
            low_current, low_previous = low_points[-1], low_points[-2]
            high_index_history.append(
                high_current.index if high_current is not None else None
            )
            low_index_history.append(
                low_current.index if low_current is not None else None
            )

            if previous_market_input is not None and market != previous_market_input:
                last_low_at_market_change = (
                    low_current.value if low_current is not None else None
                )
                last_high_at_market_change = (
                    high_current.value if high_current is not None else None
                )
            previous_market_input = market
            previous_market = market
            same_low = low_current is not None and (
                last_low_at_market_change == low_current.value
            )
            same_high = high_current is not None and (
                last_high_at_market_change == high_current.value
            )
            if not (same_low or same_high):
                if market == 1 and low_current and low_previous and high_current:
                    threshold = low_previous.value - (
                        abs(high_current.value - low_previous.value) * self.fib_factor
                    )
                    if (
                        low_current.value < low_previous.value
                        and low_current.value < threshold
                    ):
                        market = -1
                elif market == -1 and high_current and high_previous and low_current:
                    threshold = high_previous.value + (
                        abs(high_previous.value - low_current.value) * self.fib_factor
                    )
                    if (
                        high_current.value > high_previous.value
                        and high_current.value > threshold
                    ):
                        market = 1

            delayed_low_index = (
                low_index_history[bar_index - self.zigzag_len]
                if bar_index >= self.zigzag_len
                else None
            )
            delayed_high_index = (
                high_index_history[bar_index - self.zigzag_len]
                if bar_index >= self.zigzag_len
                else None
            )
            bullish_ob_index = self._select_candle(
                red_candles,
                high_previous.index if high_previous else None,
                delayed_low_index,
                bullish_ob_index,
            )
            bearish_ob_index = self._select_candle(
                green_candles,
                low_previous.index if low_previous else None,
                delayed_high_index,
                bearish_ob_index,
            )
            bearish_bb_index = self._select_candle(
                red_candles,
                high_previous.index - self.zigzag_len if high_previous else None,
                low_previous.index if low_previous else None,
                bearish_bb_index,
            )
            bullish_bb_index = self._select_candle(
                green_candles,
                low_previous.index - self.zigzag_len if low_previous else None,
                high_previous.index if high_previous else None,
                bullish_bb_index,
            )

            if market == previous_market:
                continue
            direction = "bullish" if market == 1 else "bearish"
            broken = high_previous if market == 1 else low_previous
            # A market guard can delay the transition until another opposite
            # pivot forms. Anchor lifecycle levels to the broken pivot's
            # successor, rather than to the latest opposite pivot at emission.
            after_break = pivots[broken.position + 1]
            breaking = high_current if market == 1 else low_current
            confirmation_index = pivots[breaking.position]["pivot_formation_index"]
            before_break = low_previous if market == 1 else high_previous
            is_breaker = (
                low_previous is not None and low_current.value < low_previous.value
                if market == 1
                else high_previous is not None
                and high_current.value > high_previous.value
            )
            msbs.append(
                {
                    "direction": direction,
                    "formation_index": confirmation_index,
                    "pivot_index": broken.position,
                    "kline_index": broken.index,
                    "break_level": broken.value,
                    "leg_before": (
                        before_break.index if before_break else None,
                        broken.index + 1,
                    ),
                    "leg_after": (broken.index, after_break["kline_index"] + 1),
                }
            )
            candidates = (
                (bullish_ob_index, bullish_bb_index)
                if market == 1
                else (bearish_ob_index, bearish_bb_index)
            )
            for base_index, block_type in zip(
                candidates, ("OB", "BB" if is_breaker else "MB")
            ):
                formations.append(
                    BlockFormation(
                        base_candle_index=base_index,
                        msb_kline_index=broken.index,
                        direction=direction,
                        block_type=block_type,
                        formation_index=confirmation_index,
                        invalidation_price=after_break["pivot_value"],
                        preformation_check_start_index=breaking.index,
                    )
                )

        return PineDetectionResult(
            zigzag_df=DataFrame(pivots, columns=self.PIVOT_COLUMNS),
            msbs_df=DataFrame(msbs, columns=self.MSB_COLUMNS),
            formations=formations,
        )
