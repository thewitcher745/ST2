import asyncio
from pandas import Timestamp
from websockets.asyncio.client import connect
from typing import AsyncGenerator
import json

from ..abstract_tick_provider import AbstractTickProvider
from ..tick import Tick
from src.config import Config

config = Config()


class ConnectionClosedCleanly(Exception):
    pass


class BinanceTickProvider(AbstractTickProvider):
    def __init__(self, symbols: list[str] | str):
        """
        Set up the TickProvider which would calculate the ticks, supports multiple symbols.
        """
        self._symbols: list[str]
        if isinstance(symbols, list):
            self._symbols = [symbol.lower() for symbol in symbols]
        elif isinstance(symbols, str):
            self._symbols = [symbols.lower()]

        self._listen_error: Exception | None = None
        self._times_retried: int = 0
        self._running = False
        # A flag visible to both threads which is used to gracefully stop both threads.
        self._stop_event: asyncio.Event = asyncio.Event()

    def stop(self) -> None:
        self._stop_event.set()
        self._running = False

    async def _listen(self, queue: asyncio.Queue[Tick]):
        streams = [
            f"{symbol.lower()}@kline_{config.get('timeframe')}"
            for symbol in self._symbols
        ]
        streams_string = "/".join(streams)
        url: str = config.get("binance_ws_endpoint") + "?streams=" + streams_string

        # This infinite loop tries to reconnect if the connection is severed cleanly. Otherwise it is broken.
        while True:
            self._listen_error = None
            try:
                async with connect(url, proxy=config.get("proxy_server")) as ws:
                    self._times_retried = 0
                    async for message in ws:
                        data = json.loads(message)
                        k = data["data"]["k"]
                        event_time = Timestamp(data["data"]["E"], unit="ms")
                        candle_open_time = Timestamp(k["t"], unit="ms")

                        assert isinstance(event_time, Timestamp)
                        assert isinstance(candle_open_time, Timestamp)

                        tick = Tick(
                            symbol=data["data"]["s"],
                            event_time=event_time,
                            price=float(k["c"]),
                            open=float(k["o"]),
                            high=float(k["h"]),
                            low=float(k["l"]),
                            close=float(k["c"]),
                            timestamp=candle_open_time,
                        )
                        await queue.put(tick)

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

    async def ticks(self) -> AsyncGenerator[Tick, None]:
        if self._running:
            raise RuntimeError("ticks() is already running.")
        self._running = True
        self._stop_event.clear()
        queue: asyncio.Queue[Tick] = asyncio.Queue()
        asyncio.create_task(self._listen(queue))
        while not self._stop_event.is_set():
            if self._listen_error is not None:
                raise self._listen_error
            tick = await queue.get()
            yield tick
