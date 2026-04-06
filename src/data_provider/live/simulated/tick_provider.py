"""
This module provides the "ticks" necessary for the simulation, aka the server updates
that would aggregate to the higher-timeframe data.
"""

import asyncio
from datetime import timedelta
from typing import AsyncGenerator
import numpy as np
from pandas import Timestamp

from ..tick import Tick
from src.data_provider import KLinesData
from ..abstract_tick_provider import AbstractTickProvider
from src.config import Config

config = Config()


class SimulatedTickProvider(AbstractTickProvider):
    def __init__(self, klines_data: dict[str, KLinesData]):
        """
        Set up the TickProvider which would calculate the ticks.

        Args:
            klines_data: The data that the ticks need to aggregate to.
            tick_interval: The interval, in seconds, between the ticks, default 5 seconds.
        """
        self.klines_data = klines_data  # keyed by symbol
        self.update_interval = float(config.get("update_interval"))
        self._latest_ticks: dict[str, Tick] = {}
        self._simulate_error: Exception | None = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._running = False
        self._rng = np.random.default_rng()

        for kd in klines_data.values():
            timeframe_seconds = (kd.time[1] - kd.time[0]).total_seconds()
            sim_interval = float(config.get("live_sim_tick_interval"))
            if int(timeframe_seconds // sim_interval) < 2:
                raise ValueError(
                    "Not enough ticks per candle for the given live_sim_interval."
                )

    def _candle_times(self, candle_start_time, ticks_per_candle: int) -> list:
        sim_interval = float(config.get("live_sim_tick_interval"))
        return [
            candle_start_time + timedelta(seconds=i * sim_interval)
            for i in range(ticks_per_candle)
        ]

    def _generate_candle_ticks(self, symbol: str, candle_index: int) -> list[Tick]:
        kd = self.klines_data[symbol]
        sim_interval = float(config.get("live_sim_tick_interval"))
        timeframe_seconds = (kd.time[1] - kd.time[0]).total_seconds()
        ticks_per_candle = int(timeframe_seconds // sim_interval)

        t0 = kd.time[candle_index]
        assert isinstance(t0, Timestamp)
        O = float(kd.open[candle_index])
        H = float(kd.high[candle_index])
        L = float(kd.low[candle_index])
        C = float(kd.close[candle_index])

        N = ticks_per_candle
        times = self._candle_times(t0, N)
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
        y = y + self._rng.normal(0, noise_level, N)
        y = np.clip(y, L, H)
        y[0] = O
        y[-1] = C

        return [
            Tick(
                symbol=symbol,
                event_time=times[i],
                price=float(y[i]),
                open=O,
                high=float(np.max(y[: i + 1])),
                low=float(np.min(y[: i + 1])),
                close=float(y[i]),
                timestamp=t0,
            )
            for i in range(N)
        ]

    async def _simulate_symbol(self, symbol: str, queue: asyncio.Queue[Tick]) -> None:
        try:
            sim_interval = float(config.get("live_sim_tick_interval"))
            kd = self.klines_data[symbol]
            for i in range(kd.length):
                for tick in self._generate_candle_ticks(symbol, i):
                    if self._stop_event.is_set():
                        return
                    await queue.put(tick)
                    await asyncio.sleep(sim_interval)
        except Exception as e:
            self._simulate_error = e

    async def ticks(self) -> AsyncGenerator[Tick, None]:
        if self._running:
            raise RuntimeError("ticks() is already running.")
        self._running = True
        self._stop_event.clear()
        queue: asyncio.Queue[Tick] = asyncio.Queue()
        for symbol in self.klines_data:
            asyncio.create_task(self._simulate_symbol(symbol, queue))
        while not self._stop_event.is_set():
            if self._simulate_error is not None:
                raise self._simulate_error
            tick = await queue.get()
            yield tick

    def stop(self) -> None:
        self._stop_event.set()
        self._running = False
