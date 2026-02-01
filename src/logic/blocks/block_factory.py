from pandas import DataFrame, Timestamp

from .block import Block


class BlockFactory:
    @staticmethod
    def find_last_candle_of_color(klines_df_slice: DataFrame, color: str) -> int:
        """
        Finds the last candle of a given color in a klines_df_slice.

        Args:
            klines_df_slice: A DataFrame slice of klines data.
            color: The color of the candle to find.

        Returns:
            The index of the last candle of the given color.
        """
        if color == "green":
            candles_of_color = klines_df_slice[
                klines_df_slice["close"] > klines_df_slice["open"]
            ]
        else:
            candles_of_color = klines_df_slice[
                klines_df_slice["close"] < klines_df_slice["open"]
            ]

        try:
            return int(candles_of_color.iloc[-1].name)
        except IndexError:
            return None

    @staticmethod
    def find_order_block_in_leg(
        leg_df: DataFrame,
        direction: str,
        start_time: Timestamp,
    ) -> Block | None:
        """
        This function takes a leg_df which is a slice of the klines DataFrame,
        and returns the potential order block in the leg. A bullish order block forms on the
        last red candle of the leg after the MSB, and a bearish order block forms on the
        last green candle of the leg after the MSB. The start time of the block is set to
        the candle that forms the leg that breaks and forms the MSB line.

        Args:
            leg_df: A DataFrame slice of klines data.
            direction: The direction of the order block to find, bullish or bearish.
            start_time: The time of the candle that the block is actually found.

        Returns:
            Block: The potential order block in the leg.
        """
        if direction == "bullish":
            base_candle_index = BlockFactory.find_last_candle_of_color(leg_df, "red")
        else:
            base_candle_index = BlockFactory.find_last_candle_of_color(leg_df, "green")

        # If such a candle is found, return the order block constructed on that base candle
        if base_candle_index:
            return Block(
                base_candle_index,
                base_candle_time=leg_df.loc[base_candle_index]["time"],
                direction=direction,
                block_type="OB",
                low=leg_df.loc[base_candle_index]["low"],
                high=leg_df.loc[base_candle_index]["high"],
                start_time=start_time,
            )

        else:
            return None

    @staticmethod
    def find_breaker_mitigation_block_in_leg(
        leg_df: DataFrame,
        direction: str,
        start_time: Timestamp,
    ) -> Block | None:
        """
        This function takes a leg_df which is a slice of the klines DataFrame,
        and returns the potential breaker/mitigation block in the leg. A bullish BB/MB block forms on the
        last green candle of the leg before the MSB, and a bearish BB/MB block forms on the
        last red candle of the leg before the MSB.

        Args:
            leg_df: A DataFrame slice of klines data.
            direction: The direction of the order block to find, bullish or bearish.
            start_time: The time of the candle that the block is actually found.

        Returns:
            Block: The potential mitigation block in the leg.
        """
        if direction == "bullish":
            base_candle_index = BlockFactory.find_last_candle_of_color(leg_df, "green")
        else:
            base_candle_index = BlockFactory.find_last_candle_of_color(leg_df, "red")

        # If such a candle is found, return the order block constructed on that base candle
        if base_candle_index:
            return Block(
                base_candle_index,
                base_candle_time=leg_df.loc[base_candle_index]["time"],
                direction=direction,
                block_type="BB/MB",
                low=leg_df.loc[base_candle_index]["low"],
                high=leg_df.loc[base_candle_index]["high"],
                start_time=start_time,
            )

        else:
            return None
