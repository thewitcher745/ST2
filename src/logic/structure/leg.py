"""
This module contains a small dataclass containing the data for a single leg.
"""

from dataclasses import dataclass

from src.data_provider import KLinesData


@dataclass
class Leg:
    leg_start_kline_index: int
    leg_end_kline_index: int
    klines_data: KLinesData

    def __post_init__(self):
        self.close = self.klines_data.close[
            self.leg_start_kline_index : self.leg_end_kline_index
        ]
        self.open = self.klines_data.open[
            self.leg_start_kline_index : self.leg_end_kline_index
        ]
