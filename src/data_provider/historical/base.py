from abc import abstractmethod
from datetime import timedelta
from pandas import DataFrame


class DataProvider:
    @abstractmethod
    def get_latest_klines(
        self,
        symbol: str,
        interval: str,
        time_delta: timedelta = timedelta(days=30),
    ) -> DataFrame:
        """Fetches candlestick data for a specific asset within a time range.

        This method acts as the primary interface for retrieving kline (OHLCV)
        data. It abstracts the underlying source, allowing the caller to
        request data regardless of whether it originates from a live
        exchange API or a local archival file.

        Args:
            symbol (str): The ticker symbol of the asset (e.g., 'BTCUSDT').
            interval (str): The candle timeframe (e.g., '1m', '5m', '1h').
            time_delta (timedelta, optional): The lookback period from the
                current time. Defaults to 30 days.

        Returns:
            pd.DataFrame: A standardized DataFrame containing the columns:
                'open', 'high', 'low' and 'close'. The index is a
                DatetimeIndex representing the candle open time.

        Raises:
            NotImplementedError: If the child class does not implement this method.
            ValueError: If the symbol or interval format is invalid.
        """
        raise NotImplementedError
