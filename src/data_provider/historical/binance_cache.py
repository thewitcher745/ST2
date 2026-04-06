import time
from datetime import datetime, timedelta, timezone
from binance import BinanceAPIException
from requests.exceptions import ConnectionError, ProxyError
from binance.client import Client
from pandas import DataFrame, to_datetime

from .base import DataProvider
from src.utils import BinanceDataFetchError
from src.config import Config

config = Config()


class BinanceDataProvider(DataProvider):
    def __init__(self, api_key: str = "", api_secret: str = ""):
        proxy = config.get("proxy_server")
        self.client = Client(
            api_key,
            api_secret,
            requests_params={"proxies": {"http": proxy, "https": proxy}}
            if proxy
            else {},
        )

    def get_latest_klines(
        self,
        symbol: str,
        interval: str,
        time_delta: timedelta = timedelta(days=10),
    ) -> DataFrame:
        max_retries = int(config.get("binance_cache_max_retries"))
        retry_interval = float(config.get("binance_cache_retry_interval"))

        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                # Get the current time and calculate the start and end times for the
                # historical klines request
                now = datetime.now(timezone.utc)
                start_time = (now - time_delta).timestamp() * 1000
                end_time = now.timestamp() * 1000

                # Fetch historical klines from Binance
                raw_data = self.client.get_historical_klines(
                    symbol=symbol,
                    interval=interval,
                    start_str=datetime.fromtimestamp(start_time / 1000).isoformat(),
                    end_str=datetime.fromtimestamp(end_time / 1000).isoformat(),
                )

                # Raise an exception if no data is returned
                if raw_data is None or len(raw_data) == 0:
                    raise ValueError("No data returned from Binance")

                df = DataFrame(raw_data).iloc[:, :5]  # Take first 5 columns

                # Sanitize and name the dataframe columns
                cols = ["time", "open", "high", "low", "close"]
                df.columns = cols
                df["time"] = to_datetime(df["time"], unit="ms", utc=True).dt.tz_convert(
                    None
                )
                float_cols = ["open", "high", "low", "close"]
                df[float_cols] = df[float_cols].astype(float)
                return df

            except BinanceAPIException as e:
                code = e.response.json().get("code")
                # These are permanent failures — no point retrying
                if code == -1121:
                    raise ValueError(f"Invalid symbol: {symbol}")
                if code == -1120:
                    raise ValueError(f"Invalid interval: {interval}")
                last_exception = e

            except (ConnectionError, ProxyError) as e:
                last_exception = ConnectionError(
                    f"Unable to fetch data from Binance: {e}"
                )

            except Exception as e:
                last_exception = RuntimeError(
                    f"Unexpected error in BinanceDataProvider: {e}"
                )

            print(
                f"[BinanceDataProvider] Attempt {attempt}/{max_retries} failed for {symbol}: {last_exception}. Retrying in {retry_interval}s..."
            )
            time.sleep(retry_interval)

        raise BinanceDataFetchError(
            f"Failed to fetch data for {symbol} after {max_retries} attempts. Last error: {last_exception}"
        )
