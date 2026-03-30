import asyncio
import threading
from time import sleep
from pandas import Timestamp
from websockets.asyncio.client import connect
from typing import Iterator
import json

from ..abstract_tick_provider import AbstractTickProvider
from ..tick import Tick
from ....config import Config

config = Config()


class ConnectionClosedCleanly(Exception):
    pass


class BinanceTickProvider(AbstractTickProvider):
    def __init__(self, symbol: str, min_interval: float = 0.1):
        self._symbol: str = symbol.lower()
        self._min_interval: float = min_interval
        self._latest_tick: Tick | None = None
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._thread: threading.Thread = threading.Thread(
            target=self._loop.run_forever, daemon=True
        )
        self._listen_error: Exception | None = None
        self._times_retried: int = 0
        self._running = False
        # A flag visible to both threads which is used to gracefully stop both threads.
        self._stop_event: threading.Event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()
        self._running = False

    @property
    def min_interval(self) -> float:
        return self._min_interval

    async def _listen(self):
        url: str = (
            config.get("binance_ws_endpoint")
            + f"{self._symbol.lower()}@kline_{config.get('timeframe')}"
        )
        # This infinite loop tries to reconnect if the connection is severed cleanly. Otherwise it is broken.
        while True:
            self._listen_error = None
            try:
                async with connect(url, proxy=config.get("proxy_server")) as ws:
                    self._times_retried = 0
                    async for message in ws:
                        data = json.loads(message)
                        k = data["k"]
                        event_time = Timestamp(data["E"], unit="ms")
                        candle_open_time = Timestamp(k["t"], unit="ms")

                        assert isinstance(event_time, Timestamp)
                        assert isinstance(candle_open_time, Timestamp)

                        self._latest_tick = Tick(
                            event_time=event_time,
                            price=float(k["c"]),
                            open=float(k["o"]),
                            high=float(k["h"]),
                            low=float(k["l"]),
                            close=float(k["c"]),
                            timestamp=candle_open_time,
                        )

                    # If the ws loop exits cleanly, raise our custom exception which shows a clean disconnection.
                    raise ConnectionClosedCleanly

            except ConnectionClosedCleanly:
                pass

            # If a more serious error occurs, wait some time before trying again.
            # If number of retries has exceeded max, break and raise an error.
            except Exception as e:
                self._listen_error = e
                if self._times_retried > config.get("ws_error_max_retries"):
                    break

                self._times_retried += 1
                await asyncio.sleep(config.get("ws_error_retry_interval"))

    def ticks(self) -> Iterator[Tick]:

        # If the ticks() method is already running on an instance, don't run it again.
        if self._running:
            raise RuntimeError("ticks() is already running.")
        self._running = True
        self._stop_event.clear()

        # start the WS listener as a background task, yield the latest result at every sleep
        update_interval: float = float(config.get("update_interval"))
        if update_interval < float(config.get("binance_kline_update_interval")):
            raise ValueError(
                "Update interval can't be less than two consecutive Binance ticks."
            )

        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        asyncio.run_coroutine_threadsafe(self._listen(), self._loop)

        while not self._stop_event.is_set():
            if self._listen_error is not None:
                raise self._listen_error
            if self._latest_tick is not None:
                yield self._latest_tick
            sleep(update_interval)
