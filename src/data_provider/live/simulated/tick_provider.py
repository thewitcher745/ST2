"""
This module provides the "ticks" necessary for the simulation, aka the server updates
that would aggregate to the higher-timeframe data.
"""

from datetime import timedelta
from typing import Iterator
import numpy as np

from ..tick import Tick
from ..abstract_tick_provider import AbstractTickProvider
from ...historical import KLinesData


class SimulatedTickProvider(AbstractTickProvider):
    def __init__(self, klines_data: KLinesData, tick_interval: float = 0.1):
        """
        Set up the TickProvider which would calculate the ticks.

        Args:
            klines_data: The data that the ticks need to aggregate to.
            tick_interval: The interval, in seconds, between the ticks, default 5 seconds.
        """
        self.klines_data = klines_data
        self._min_interval = tick_interval

        timeframe_seconds = (klines_data.time[1] - klines_data.time[0]).total_seconds()
        self.candle_duration_seconds = timeframe_seconds
        self.ticks_per_candle = int(self.candle_duration_seconds // self._min_interval)
        if self.ticks_per_candle < 2:
            raise ValueError("Not enough ticks per candle for the given tick_interval.")

        self._rng = np.random.default_rng()

    @property
    def min_interval(self) -> float:
        return self._min_interval

    def _candle_times(self, candle_start_time) -> list:
        return [
            candle_start_time + timedelta(seconds=i * self.min_interval)
            for i in range(self.ticks_per_candle)
        ]

    def _generate_candle_ticks(self, candle_index: int) -> list[Tick]:
        t0 = self.klines_data.time[candle_index]
        O = float(self.klines_data.open[candle_index])
        H = float(self.klines_data.high[candle_index])
        L = float(self.klines_data.low[candle_index])
        C = float(self.klines_data.close[candle_index])

        N = self.ticks_per_candle
        times = self._candle_times(t0)
        x = np.arange(N, dtype=float)

        idx_h = self._rng.integers(1, N - 1)
        idx_l = self._rng.integers(1, N - 1)
        while idx_l == idx_h:
            idx_l = self._rng.integers(1, N - 1)

        idx_h = max(1, min(N - 2, idx_h))
        idx_l = max(1, min(N - 2, idx_l))

        anchor_points = {0: O, N - 1: C, idx_h: H, idx_l: L}
        x_anchor = np.array(sorted(anchor_points.keys()), dtype=float)
        y_anchor = np.array([anchor_points[int(k)] for k in x_anchor], dtype=float)

        y = np.interp(x, x_anchor, y_anchor)

        noise_level = 0.01 * (H - L)
        noise = self._rng.normal(0, noise_level, N)
        y = y + noise
        y = np.clip(y, L, H)

        y[0] = O
        y[-1] = C

        ticks = []
        for i in range(N):
            ticks.append(
                Tick(
                    event_time=times[i],
                    price=float(y[i]),
                    open=O,
                    high=float(np.max(y[: i + 1])),
                    low=float(np.min(y[: i + 1])),
                    close=float(y[i]),
                    timestamp=t0,
                )
            )
        return ticks

    def ticks(self) -> Iterator[Tick]:
        for i in range(self.klines_data.length):
            for tick in self._generate_candle_ticks(i):
                yield tick
