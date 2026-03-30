"""
This folder contains code to connect to the actual Binance websocket to fetch live data.
"""

from .tick_provider import BinanceTickProvider

__all__ = ["BinanceTickProvider"]
