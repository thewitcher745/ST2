from datetime import datetime, timedelta, timezone
from binance import BinanceAPIException
from requests.exceptions import ConnectionError, ProxyError
from binance.client import Client
from pandas import DataFrame, to_datetime

from .base import DataProvider
from ...config import Config

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
            if raw_data is None:
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
            if e.response.json()["code"] == -1121:
                raise ValueError(f"Invalid symbol: {symbol}")
            if e.response.json()["code"] == -1120:
                raise ValueError(f"Invalid interval: {interval}")
        except (ConnectionError, ProxyError) as e:
            raise ConnectionError(f"Unable to fetch data from Binance: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error in BinanceDataProvider: {e}")

        return DataFrame(columns=[])
