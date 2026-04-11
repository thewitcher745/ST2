import time
from datetime import datetime, timedelta, timezone
from binance import BinanceAPIException, HistoricalKlinesType
from requests.exceptions import ConnectionError, ProxyError
from binance.client import Client
from pandas import DataFrame, to_datetime
import logging

from .base import DataProvider
from src.utils import BinanceDataFetchError
from src.config import Config

logger = logging.getLogger("[BinanceDataProvider]")
config = Config()


class BinanceDataProvider(DataProvider):
    def __init__(self, api_key: str = "", api_secret: str = ""):
        proxy = config.get_optional("proxy_server")
        max_retries = int(config.get("binance_cache_max_retries"))
        retry_interval = float(config.get("binance_cache_retry_interval"))

        last_exception = None

        for attempt in range(1, max_retries + 1):
            try:
                self.client = Client(
                    api_key,
                    api_secret,
                    requests_params={"proxies": {"http": proxy, "https": proxy}}
                    if proxy
                    else {},
                )
                # Success, exit retry loop
                return

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Attempt {attempt}/{max_retries} failed "
                    f"to initialize Binance client: {e}. "
                    f"Retrying in {retry_interval}s..."
                )

                if attempt < max_retries:
                    time.sleep(retry_interval)

        # If we get here, all retries failed
        raise RuntimeError(
            f"Failed to initialize Binance client after {max_retries} attempts"
        ) from last_exception

    def get_latest_klines(
        self,
        symbol: str,
        interval: str,
        time_delta: timedelta = timedelta(days=10),
        limit: int | None = None,
        most_recent: bool = False,
        include_live_candle: bool = False,
    ) -> DataFrame:
        """
        Fetches historical KLines.

        most_recent: If set, the start_time argument isn't passed to the fetching method, resulting in returning "limit" recent KLines
        include_live_candle: If set to True, will include the latest (live open) candle in the returned DataFrame.
        """
        max_retries = int(config.get("binance_cache_max_retries"))
        retry_interval = float(config.get("binance_cache_retry_interval"))

        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                # Get the current time and calculate the start and end times for the
                # historical klines request
                now = datetime.now(timezone.utc)
                start_time = (now - time_delta).timestamp() * 1000
                # Fetch historical klines from Binance
                # If most_recent is true, the start time is ignored.
                start_str = (
                    datetime.fromtimestamp(start_time / 1000).isoformat()
                    if not most_recent
                    else None
                )
                raw_data = self.client.get_historical_klines(
                    symbol=symbol,
                    interval=interval,
                    start_str=start_str,
                    klines_type=HistoricalKlinesType.FUTURES,
                    limit=limit,
                )

                # Raise an exception if no data is returned
                if raw_data is None or len(raw_data) == 0:
                    raise ValueError("No data returned from Binance")
                # Take first 5 columns.
                # The very last candle in the Binance response is the currently open candle. Included if the
                # related boolean is passed as an argument, typically in a forward test environment.
                if include_live_candle:
                    df = DataFrame(raw_data).iloc[:, :5]
                else:
                    df = DataFrame(raw_data).iloc[:-1, :5]

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

            logger.warning(
                f"Attempt {attempt}/{max_retries} failed for {symbol}: {last_exception}. Retrying in {retry_interval}s..."
            )
            time.sleep(retry_interval)

        raise BinanceDataFetchError(
            f"Failed to fetch data for {symbol} after {max_retries} attempts. Last error: {last_exception}"
        )
