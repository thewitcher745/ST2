from pandas import DataFrame
import numpy as np

from .block_factory import BlockFactory
from ..utils import convert_pivot_to_kline


class BlockManager:
    """The 'Orchestrator' that iterates over MSBs and manages the block list."""

    def __init__(self):
        self.factory = BlockFactory()
        self.active_blocks = []
        
    def add_blocks(
        self, msbs_df: DataFrame, zigzag_df: DataFrame, klines_df: DataFrame
    ) -> None:
        """
        This is your iteration logic. It processes the MSB signals
        and populates the block list.
        """
        new_blocks = []
        for _, row in msbs_df.iterrows():
            # Slice the leg before the break
            start, end = row["leg_after"]
            leg_data = klines_df.loc[start:end]

            # The index and time of the candle which creates the MSB.
            start_index = row["formation_index"]
            start_time = klines_df.loc[row["formation_index"]]["time"]

            # Initially when the block forms, its invalidation price level should be the price value of the pivot
            # succeeding the pivot which the MSB is located. If a candle "CLOSES" above/below this price, the block is
            # deemed invalid.
            next_pivot_kline = convert_pivot_to_kline(
                row["pivot_index"] + 1, zigzag_df, klines_df
            )

            if row["direction"] == "bullish":
                invalidation_price = next_pivot_kline.low
            else:
                invalidation_price = next_pivot_kline.high

            ob = self.factory.find_order_block_in_leg(
                leg_data, str(row["direction"]), start_time
            )
            if ob:
                # Logic for setting the end time of the block
                # The end time of the block happens when the price breaks through the invalidation
                # price of the block.
                closes_after_start_array = np.array(klines_df.close)[start_index:]

                # The index of the candle which invalidates the block. Since the np.where command
                # outputs an int which is "local" to the array (index-less), it has to be offset
                # by te start_index.
                if row["direction"] == "bullish":
                    invalidating_closes = np.where(
                        closes_after_start_array < invalidation_price
                    )[0]
                else:
                    invalidating_closes = np.where(
                        closes_after_start_array > invalidation_price
                    )[0]
                if len(invalidating_closes > 0):
                    invalidating_candle_index = start_index + invalidating_closes[0]
                    # If an invalidating candle has been found, set its time to the end time of the
                    # block.
                    ob.end_time = klines_df.iloc[invalidating_candle_index].time

                new_blocks.append(ob)

            bb = self.factory.find_breaker_mitigation_block_in_leg(
                leg_data, str(row["direction"]), start_time
            )
            if bb:
                # Logic for setting the end time of the block
                # The end time of the block happens when the price breaks through the invalidation
                # price of the block.
                closes_after_start_array = np.array(klines_df.close)[start_index:]

                # The index of the candle which invalidates the block. Since the np.where command
                # outputs an int which is "local" to the array (index-less), it has to be offset
                # by te start_index.
                if row["direction"] == "bullish":
                    invalidating_closes = np.where(
                        closes_after_start_array < invalidation_price
                    )[0]
                else:
                    invalidating_closes = np.where(
                        closes_after_start_array > invalidation_price
                    )[0]
                if len(invalidating_closes > 0):
                    invalidating_candle_index = start_index + invalidating_closes[0]
                    # If an invalidating candle has been found, set its time to the end time of the
                    # block.
                    bb.end_time = klines_df.iloc[invalidating_candle_index].time

                new_blocks.append(bb)

        self.active_blocks.extend(new_blocks)
