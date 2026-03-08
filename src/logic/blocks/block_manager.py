from pandas import DataFrame
from line_profiler import profile

from .block import Block
from .block_factory import BlockFactory
from ..utils import convert_pivot_to_kline


class BlockManager:
    """The 'Orchestrator' that manages the block list."""

    def __init__(self):
        self.factory = BlockFactory()
        self.all_blocks: dict[str, list[Block]] = {"bullish": [], "bearish": []}
        self.active_blocks: dict[str, list[Block]] = {"bullish": [], "bearish": []}

    def add_blocks(
        self, msbs_df: DataFrame, zigzag_df: DataFrame, klines_df: DataFrame
    ) -> None:
        """
        This is your iteration logic. It processes the MSB signals
        and populates the block list.
        """
        for _, row in msbs_df.iterrows():
            direction = row["direction"]
            # Slice the leg before the break
            # "before" is the leg that ends at the MSB, "after" is the leg that starts with the MSB
            start_before, end_before = row["leg_before"]
            start_after, end_after = row["leg_after"]

            leg_before_data = klines_df.loc[start_before:end_before]
            leg_after_data = klines_df.loc[start_after:end_after]

            # The index and time of the candle which creates the MSB.
            start_time = klines_df.loc[row["formation_index"]]["time"]

            # Initially when the block forms, its invalidation price level should be the price value of the pivot
            # succeeding the pivot which the MSB is located. If a candle "CLOSES" above/below this price, the block is
            # deemed invalid.
            next_pivot_kline = convert_pivot_to_kline(
                row["pivot_index"] + 1, zigzag_df, klines_df
            )

            if direction == "bullish":
                invalidation_price = next_pivot_kline.low
            else:
                invalidation_price = next_pivot_kline.high

            ob = self.factory.find_order_block_in_leg(
                leg_after_data, direction, start_time, invalidation_price
            )
            bb = self.factory.find_breaker_mitigation_block_in_leg(
                leg_before_data, direction, start_time, invalidation_price
            )

            # Since BB/MB's come before OB's, it's better to add them first for good measure.
            if bb:
                self.active_blocks[direction].append(bb)
                self.all_blocks[direction].append(bb)
            if ob:
                self.active_blocks[direction].append(ob)
                self.all_blocks[direction].append(ob)

    @profile
    def update_block_end_times(self, klines_df: DataFrame):
        """
        This method updates each block's end time. The logic is that whenever a the pivot after
        the MSB is broken by a candle closing above/below it, the block AND ANY BLOCK OF THE SAME
        DIRECTION BEFORE IT is considered "ended".
        """

        # Iterate through all blocks, using a while loop.
        # Since the list containing the blocks is modified, using a for loop is not good practice.
        klines_df_time_array = klines_df.time.to_numpy()
        klines_df_close_array = klines_df.close.to_numpy()
        for direction in ["bullish", "bearish"]:
            # block_counter = 0
            # while block_counter < len(self.all_blocks[direction]):
            #     current_invalidation_price = self.all_blocks[direction][block_counter]

            for block_counter, block in enumerate(self.all_blocks[direction]):
                current_end_index = block.check_end_candle(klines_df_close_array)

                if current_end_index:
                    current_end_time = klines_df_time_array[current_end_index]
                    # Set the end index and end time for the current block.
                    block.end_index = current_end_index
                    block.end_time = current_end_time

                    # If we are checking the first block (of each direction), since there are no blocks before
                    # it, only set the block's own end time and index and continue to the next iteration to
                    # prevent unnecessary complications.
                    if block_counter == 0:
                        continue

                    # For the old blocks, if the old block doesn't have an end time, or has an end time
                    # after the current end time, set its end time to the current.
                    for old_block in self.all_blocks[direction][: block_counter - 1]:
                        if (
                            not old_block.end_index
                            or old_block.end_index > current_end_index
                        ):
                            old_block.end_index = current_end_index
                            old_block.end_time = current_end_time
