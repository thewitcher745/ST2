from datetime import datetime, timedelta
import os
from pandas import DataFrame, read_feather

from .binance_cache import BinanceDataProvider
from .base import DataProvider
from src.config import Config

config = Config()


class LocalDataProvider(DataProvider):
    def __init__(
        self,
        cache_parent_dir=f"data/klines/{config.run_id}",
        live_data_provider=BinanceDataProvider,
    ):
        """
        Uses a live data provider to fetch data and caches it locally.
        """
        self.cache_parent_dir = cache_parent_dir

        # Make sure the caching directory exists
        os.makedirs(self.cache_parent_dir, exist_ok=True)
        self.live_data_provider = live_data_provider

    def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
    ) -> DataFrame:
        file_name = f"{symbol}_{interval}_{start_time.isoformat()}_{end_time.isoformat()}.feather"
        file_path = os.path.join(self.cache_parent_dir, file_name)

        # Fetch data and cache it if a local cache doesn't exist
        if not os.path.exists(file_path):
            # Fetch data from live provider and cache it
            data = self.live_data_provider().get_klines(
                symbol, interval, start_time, end_time
            )

            # Save the data to the file
            data.to_feather(file_path)

            return data

        # Load data from cache
        return read_feather(file_path)

    def get_latest_klines(
        self, symbol: str, interval: str, time_delta: timedelta = timedelta(days=10)
    ) -> DataFrame:
        file_name = f"{symbol}_{interval}.feather"
        file_path = os.path.join(self.cache_parent_dir, file_name)

        # Fetch live data and cache it if a local cache doesn't exist
        if not os.path.exists(file_path):
            # Fetch data from live provider and cache it
            data = self.live_data_provider().get_latest_klines(
                symbol, interval, time_delta
            )

            # Save the data to the file
            data.to_feather(file_path)

            return data

        # Load data from cache
        return read_feather(file_path)
