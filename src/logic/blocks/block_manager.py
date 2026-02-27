from pandas import DataFrame

from .block_factory import BlockFactory


class BlockManager:
    """The 'Orchestrator' that iterates over MSBs and manages the block list."""

    def __init__(self):
        self.factory = BlockFactory()
        self.active_blocks = []

    def add_obs(self, msbs_df: DataFrame, klines_df: DataFrame) -> None:
        """
        This is your iteration logic. It processes the MSB signals
        and populates the block list.
        """
        new_blocks = []
        for _, row in msbs_df.iterrows():
            # Slice the leg before the break
            start, end = row["leg_after"]
            leg_data = klines_df.loc[start:end]
            start_time = klines_df.loc[row["formation_index"]]["time"]
            # Logic for multiple block types can go here:
            ob = self.factory.find_order_block_in_leg(
                leg_data, str(row["direction"]), start_time
            )
            if ob:
                new_blocks.append(ob)

        self.active_blocks.extend(new_blocks)

    def add_bbs(self, msbs_df: DataFrame, klines_df: DataFrame) -> None:
        """
        This is your iteration logic. It processes the MSB signals
        and populates the block list.
        """
        new_blocks = []
        for _, row in msbs_df.iterrows():
            # Slice the leg before the break
            start, end = row["leg_before"]
            leg_data = klines_df.loc[start:end]
            start_time = klines_df.loc[row["formation_index"]]["time"]

            # Logic for multiple block types can go here:
            ob = self.factory.find_breaker_mitigation_block_in_leg(
                leg_data, str(row["direction"]), start_time
            )
            if ob:
                new_blocks.append(ob)

        self.active_blocks.extend(new_blocks)
