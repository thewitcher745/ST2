from datetime import timedelta


class BinanceDataFetchError(Exception):
    """Raised when Binance data fetching fails after all retries."""

    pass


def convert_timeframe_to_timedelta(timeframe: str) -> timedelta:
    if timeframe.endswith("s"):
        numeric_value = int(timeframe.replace("s", ""))
        return timedelta(seconds=numeric_value)
    elif timeframe.endswith("m"):
        numeric_value = int(timeframe.replace("m", ""))
        return timedelta(minutes=numeric_value)
    elif timeframe.endswith("h"):
        numeric_value = int(timeframe.replace("h", ""))
        return timedelta(hours=numeric_value)
    elif timeframe.endswith("d"):
        numeric_value = int(timeframe.replace("d", ""))
        return timedelta(days=numeric_value)
    elif timeframe.endswith("w"):
        numeric_value = int(timeframe.replace("w", ""))
        return timedelta(weeks=numeric_value)
    else:
        raise ValueError("Invalid timeframe definition.")
