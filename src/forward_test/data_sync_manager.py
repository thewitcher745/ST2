"""
This module contains data syncing and resyncing methods and utilities. These tools will ensure the data received by
the forward test is in sync with the Binance server.
"""

import logging

from datetime import timedelta
from src.data_provider import BinanceDataProvider, LiveKLinesData, Tick
from src.config import Config
from src.utils import BinanceDataFetchError, convert_timeframe_to_timedelta

config = Config()
logger = logging.getLogger("[DataSyncManager]")


class DataSyncManager:
    def __init__(self, symbols: list[str], data_provider=BinanceDataProvider):
        self._symbols = symbols
        self.data_provider = data_provider()
        self.klines_data: dict[str, LiveKLinesData] = {}

    def load_klines(self) -> list[str]:
        """Loads KLines from Binance, Returns a list of faulty symbols."""
        faulty_symbols: list[str] = []
        for symbol in self._symbols:
            try:
                klines_df = self.data_provider.get_latest_klines(
                    symbol,
                    interval=config.get("timeframe"),
                    time_delta=timedelta(days=int(config.get("startup_n_days"))),
                    include_live_candle=True,
                )
                self.klines_data[symbol] = LiveKLinesData(klines_df)
                logger.debug(
                    f"[startup] Fetched {self.klines_data[symbol].length} KLines for symbol {symbol}"
                )
            except BinanceDataFetchError as e:
                logger.warning(f"[startup] Giving up on {symbol} after retries: {e}")
                faulty_symbols.append(symbol)
            except Exception as e:
                logger.warning(f"[startup] Failed to initialize {symbol}: {e}")
                faulty_symbols.append(symbol)

        return faulty_symbols

    def _resync_data(self, tick: Tick) -> None:
        """
        Resyncs the KLines with the server by fetching a number of the most recent candles.
        """
        logger.debug("------RESYNC------")
        logger.debug(
            f"Incoming tick timestamp is {tick.timestamp} (vs. {self.klines_data[tick.symbol].live_candle_time} on local)"
        )

        symbol = tick.symbol
        # 1. Find the amount of time that has passed since the last "closed" candle of the dataset.
        time_elapsed: timedelta = (
            tick.timestamp - self.klines_data[symbol].last_closed_time
        )

        # 2. Find how many klines we need to fetch, and add a fixed buffer to it for safety.
        timeframe = config.get("timeframe")
        candle_timedelta = convert_timeframe_to_timedelta(timeframe)
        # The resync buffer is a safety margin we add to each fetch to mend any possible inconsistency in the data
        resync_buffer = int(config.get("binance_cache_resync_buffer"))
        n_klines = int(time_elapsed / candle_timedelta) + resync_buffer
        logger.debug(f"{n_klines} candles to fetch.")

        # 3. Resync the KLinesData using the data just fetched.
        # If the gap is too large, replace everything.
        if n_klines >= self.klines_data[symbol].length:
            incoming_klines_data = self.data_provider.get_latest_klines(
                symbol,
                interval=timeframe,
                time_delta=timedelta(days=int(config.get("startup_n_days"))),
                include_live_candle=True,
            )
            self.klines_data[symbol].replace(incoming_klines_data)
        else:
            incoming_klines_data = self.data_provider.get_latest_klines(
                symbol,
                timeframe,
                limit=n_klines,
                most_recent=True,
                include_live_candle=True,
            )
            self.klines_data[symbol].replace(incoming_klines_data, partial=True)
        logger.debug(f"Fetched {len(incoming_klines_data)} candles and resynced data.")

    def process_tick(self, tick: Tick) -> bool:
        """
        Processes the tick, resyncs the data if necessary or updates the latest tick.
        Returns True if the processing is successful, False if not.
        """
        # If we are still in the same candle, update it
        if tick.timestamp == self.klines_data[tick.symbol].live_candle_time:
            self.klines_data[tick.symbol].update(tick)
            return True
        # Otherwise, resync the last few candles with the server
        else:
            try:
                self._resync_data(tick)
            except BinanceDataFetchError as e:
                logger.warning(f"Failed to resync {tick.symbol}: {e}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error for {tick.symbol}: {e}")
                return False
            return True
