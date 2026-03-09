from pandas import Timestamp
import numpy as np

from ..structure.leg import Leg
from ...data_provider import KLinesData
from .block import Block


class BlockFactory:
    @staticmethod
    def find_last_candle_of_color(leg: Leg, color: str) -> int:
        """
        Finds the last candle of a given color in a Leg.

        Args:
            leg: A Leg object containing the open and close values in a leg, including its start index.
            color: The color of the candle to find.

        Returns:
            The index of the last candle of the given color.
        """
        green_bool_filter = leg.close > leg.open
        red_bool_filter = ~green_bool_filter

        if color == "green":
            candles_of_color = np.where(green_bool_filter)[0]
        else:
            candles_of_color = np.where(red_bool_filter)[0]

        try:
            return int(candles_of_color[-1] + leg.leg_start_kline_index)
        except IndexError:
            return None

    @staticmethod
    def find_order_block_in_leg(
        leg: Leg,
        klines_data: KLinesData,
        direction: str,
        start_index: int,
        start_time: Timestamp,
        invalidation_price: float,
    ) -> Block | None:
        """
        This function takes a leg which is a Leg object, essentially a slice of a KLines dataframe,
        and returns the potential order block in the leg. A bullish order block forms on the
        last red candle of the leg after the MSB, and a bearish order block forms on the
        last green candle of the leg after the MSB. The start time of the block is set to
        the candle that forms the leg that breaks and forms the MSB line.

        Args:
            leg: A Leg object containing the open and close values in a leg, including its start index.
            direction: The direction of the order block to find, bullish or bearish.
            start_index: The index of the candle that the block is actually found.
            start_time: The time of the candle that the block is actually found.
            invalidation_price: The price value at which the MSB that formed the block is considered invalid.

        Returns:
            Block: The potential order block in the leg.
        """
        if direction == "bullish":
            base_candle_index = BlockFactory.find_last_candle_of_color(leg, "red")
        else:
            base_candle_index = BlockFactory.find_last_candle_of_color(leg, "green")

        # If such a candle is found, return the order block constructed on that base candle
        if base_candle_index:
            return Block(
                base_candle_index,
                base_candle_time=klines_data.time[base_candle_index],
                direction=direction,
                block_type="OB",
                low=klines_data.low[base_candle_index],
                high=klines_data.high[base_candle_index],
                start_index=start_index,
                start_time=start_time,
                invalidation_price=invalidation_price,
            )

        else:
            return None

    @staticmethod
    def find_breaker_mitigation_block_in_leg(
        leg: Leg,
        klines_data: KLinesData,
        direction: str,
        start_index: int,
        start_time: Timestamp,
        invalidation_price: float,
    ) -> Block | None:
        """
        This function takes a leg which is a Leg object, essentially a slice of a KLines dataframe,
        and returns the potential breaker/mitigation block in the leg. A bullish BB/MB block forms on the
        last green candle of the leg before the MSB, and a bearish BB/MB block forms on the
        last red candle of the leg before the MSB.

        Args:
            leg: A Leg object containing the open and close values in a leg, including its start index.
            direction: The direction of the order block to find, bullish or bearish.
            start_index: The index of the candle that the block is actually found.
            start_time: The time of the candle that the block is actually found.
            invalidation_price: The price value at which the MSB that formed the block is considered invalid.

        Returns:
            Block: The potential mitigation block in the leg.
        """
        if direction == "bullish":
            base_candle_index = BlockFactory.find_last_candle_of_color(leg, "green")
        else:
            base_candle_index = BlockFactory.find_last_candle_of_color(leg, "red")

        # If such a candle is found, return the order block constructed on that base candle
        if base_candle_index:
            return Block(
                base_candle_index,
                base_candle_time=klines_data.time[base_candle_index],
                direction=direction,
                block_type="BB/MB",
                low=klines_data.low[base_candle_index],
                high=klines_data.high[base_candle_index],
                start_index=start_index,
                start_time=start_time,
                invalidation_price=invalidation_price,
            )

        else:
            return None
