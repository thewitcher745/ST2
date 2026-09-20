from typing import Literal
from pandas import DataFrame, Timestamp

from src.data_provider import KLinesData
from src.config import Config
from .block import Block
from .block_factory import BlockFactory
from ..structure.leg import Leg

config = Config()


def is_block_height_percentage_valid(block: Block):
    """
    Checks if the height percentage of a block (of any type, OB/BB/MB) is within
    the range specified by min_block_height_percentage and max_block_height_percentage.
    """
    return (
        config.min_block_height_percentage
        <= block.height_percentage
        <= config.max_block_height_percentage
    )


def is_block_formation_valid_vs_price_action(
    block: Block, klines_data: KLinesData, start_index: int
):
    """
    Checks if the candle right at the block's base has pierced it at formation time.
    """
    start_index = block.start_index
    if block.direction == "bullish":
        return klines_data.low[start_index] > block.high
    else:
        return klines_data.high[start_index] < block.low


class BlockManager:
    """The 'Orchestrator' that manages the block list."""

    def __init__(self):
        self.factory = BlockFactory()
        self.all_blocks: dict[str, list[Block]] = {"bullish": [], "bearish": []}
        self.active_blocks: dict[str, list[Block]] = {"bullish": [], "bearish": []}
        # The timestamp of the first active block's forming MSB
        # This is used for the forward test and before this timestamp MSB's aren't added to all blocks.
        # It's just an optimization step to avoid repeating old, ended blocks.
        self._first_active_block_msb_index: dict[str, None | int] = {
            "bullish": None,
            "bearish": None,
        }

    def reset_blocks(self):
        self.all_blocks = {"bullish": [], "bearish": []}
        self.active_blocks = {"bullish": [], "bearish": []}

    @property
    def all_active_blocks_aslist(self) -> list[Block]:
        """Returns the active blocks as a list without direction separation."""
        return self.active_blocks["bullish"] + self.active_blocks["bearish"]

    @property
    def all_blocks_aslist(self) -> list[Block]:
        """Returns all blocks as a list without direction separation."""
        return self.all_blocks["bullish"] + self.all_blocks["bearish"]

    def update_blocks(
        self, msbs_df: DataFrame, zigzag_df: DataFrame, klines_data: KLinesData
    ) -> None:
        """
        This is the iteration logic. It processes the MSB signals and populates the block list.
        """
        self.reset_blocks()
        for _, row in msbs_df.iterrows():
            direction: Literal["bullish", "bearish"] = row["direction"]  # type: ignore[assignment]

            # If a direction is specified, ignore the MSB's in other directions
            if config.direction == "long" and direction == "bearish":
                continue
            if config.direction == "short" and direction == "bullish":
                continue

            # If the MSB being processed has a KLine index earlier than that of the first active block found in
            # older iterations of the forward test, completely skip adding it to the list. Only do this if
            # the first active block msb index is registered already.
            truncation_index = self._first_active_block_msb_index[direction]
            msb_kline_index = row["kline_index"]
            assert isinstance(msb_kline_index, int)
            if truncation_index is not None:
                if msb_kline_index < truncation_index:
                    continue

            # Slice the leg before the break
            # "before" is the leg that ends at the MSB, "after" is the leg that starts with the MSB
            start_before, end_before = row["leg_before"]
            start_after, end_after = row["leg_after"]

            leg_before_data = Leg(start_before, end_before, klines_data)
            leg_after_data = Leg(start_after, end_after, klines_data)

            # The index and time of the candle which creates the MSB.
            start_time = klines_data.time[row["formation_index"]]
            assert isinstance(start_time, Timestamp)

            # Initially when the block forms, its invalidation price level should be the price value of the pivot
            # succeeding the pivot which the MSB is located. If a candle "CLOSES" above/below this price, the block is
            # deemed invalid.
            if direction == "bullish":
                invalidation_price = klines_data.low[
                    zigzag_df.iloc[row["pivot_index"] + 1].kline_index
                ]
            else:
                invalidation_price = klines_data.high[
                    zigzag_df.iloc[row["pivot_index"] + 1].kline_index
                ]
            assert isinstance(invalidation_price, float)

            formation_index = row["formation_index"]
            assert isinstance(formation_index, int)

            msb_kline_index = row["kline_index"]
            assert isinstance(msb_kline_index, int)

            ob = None
            if "OB" in config.block_types or config.block_types is None:
                ob = self.factory.find_order_block_in_leg(
                    msb_kline_index,
                    leg_after_data,
                    klines_data,
                    direction,
                    formation_index,
                    start_time,
                    invalidation_price,
                )
            # The BB/MB property of the block depends on if the pivot after the MSB pivot is a lower low
            # or a higher low. A lower low results in a BB and a higher low results in an MB.
            msb_next_pivot_structure = zigzag_df.iloc[row["pivot_index"] + 1].structure
            bb = None
            mb = None
            if msb_next_pivot_structure == "LL" or msb_next_pivot_structure == "HH":
                if "BB" in config.block_types or config.block_types is None:
                    bb = self.factory.find_breaker_mitigation_block_in_leg(
                        msb_kline_index,
                        leg_before_data,
                        klines_data,
                        direction,
                        formation_index,
                        start_time,
                        invalidation_price,
                        type="BB",
                    )
            else:
                if "MB" in config.block_types or config.block_types is None:
                    mb = self.factory.find_breaker_mitigation_block_in_leg(
                        msb_kline_index,
                        leg_before_data,
                        klines_data,
                        direction,
                        formation_index,
                        start_time,
                        invalidation_price,
                        type="MB",
                    )

            # Since BB/MB's come before OB's, it's better to add them first for good measure.
            # Also check if the blocks are in the valid range, as defined by config variables
            # min_block_height_percentage and max_block_height_percentage
            if bb is not None:
                if is_block_height_percentage_valid(
                    bb
                ) and is_block_formation_valid_vs_price_action(
                    bb, klines_data, bb.start_index
                ):
                    self.all_blocks[direction].append(bb)
            if mb is not None:
                if is_block_height_percentage_valid(
                    mb
                ) and is_block_formation_valid_vs_price_action(
                    mb, klines_data, mb.start_index
                ):
                    self.all_blocks[direction].append(mb)
            if ob is not None:
                if is_block_height_percentage_valid(
                    ob
                ) and is_block_formation_valid_vs_price_action(
                    ob, klines_data, ob.start_index
                ):
                    self.all_blocks[direction].append(ob)

    def update_block_end_times(self, klines_data: KLinesData):
        """
        This method updates each block's end time. The logic is that whenever a the pivot after
        the MSB is broken by a candle closing above/below it, the block AND ANY BLOCK OF THE SAME
        DIRECTION BEFORE IT is considered "ended".
        """

        # Iterate through all blocks, using a while loop.
        # Since the list containing the blocks is modified, using a for loop is not good practice.
        for direction in ["bullish", "bearish"]:
            # block_counter = 0
            # while block_counter < len(self.all_blocks[direction]):
            #     current_invalidation_price = self.all_blocks[direction][block_counter]

            for block_counter, block in enumerate(self.all_blocks[direction]):
                # ------------- Uses shadows for cancellations -------------
                # end_check_window = (
                #     klines_data.high
                #     if block.direction == "bearish"
                #     else klines_data.low
                # )
                # current_end_index = block.check_end_candle(end_check_window)

                # ------------- Uses fully closed candles for cancellations -------------
                end_check_window = klines_data.close
                # It's +1 since in an actual forward test scenario we would wait for th candle to fully close first
                current_end_index = block.check_end_candle(end_check_window)
                if current_end_index:
                    # If the end index found (with the +1 added) is larger than the klines_data length (which would pretty
                    # much only happen in forward test scenario) we just wait longer for the next candle to form.
                    current_end_index += 1
                    if current_end_index >= klines_data.length:
                        continue

                if current_end_index:
                    current_end_time = klines_data.time[current_end_index]
                    # Set the end index and end time for the current block.
                    block.end_index = current_end_index
                    assert isinstance(current_end_time, Timestamp)
                    block.end_time = current_end_time

                    # If we are checking the first block (of each direction), since there are no blocks before
                    # it, only set the block's own end time and index and continue to the next iteration to
                    # prevent unnecessary complications.
                    if block_counter == 0:
                        continue

                    # For the old blocks, if the old block doesn't have an end time, or has an end time
                    # after the current end time, set its end time to the current.
                    for old_block in self.all_blocks[direction]:
                        # Skip the block if it has a more recent start index. Basically only do this for
                        # older boxes
                        if not old_block.start_index <= block.start_index:
                            continue

                        if (
                            not old_block.end_index
                            or old_block.end_index > current_end_index
                        ):
                            old_block.end_index = current_end_index
                            old_block.end_time = current_end_time

                        # Remove the old block from the list of active blocks, if there, aka update the list of active blocks.
                        if old_block in self.active_blocks[direction]:
                            self.active_blocks[direction].remove(old_block)

                # If no end index is found, it means the block has not ended yet, meaning it is still active.
                # This is only useful for the forward test basically.
                else:
                    self.active_blocks[direction].append(block)

            # At the end, register the MSB index of the earliest active block. This is used for the forward test.
            if len(self.active_blocks[direction]) > 0:
                self._first_active_block_msb_index[direction] = self.active_blocks[
                    direction
                ][0].msb_kline_index
