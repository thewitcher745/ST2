"""
Handles initial calculation and recalculations.
"""

from datetime import datetime

from src.data_provider import KLinesData
from src.logic import BlockManager, MSBIdentifier, PositionManager, Zigzag
from src.config import Config

config = Config()


class StructureCalculator:
    def __init__(self):
        pass

    def _recalculate(
        self,
        klines_data: KLinesData,
        zigzag: Zigzag,
        block_manager: BlockManager,
        position_manager: PositionManager,
        msb_identifier: MSBIdentifier,
    ) -> None:
        """
        Recalculates the logic of the strategy with a given symbol. The data is fetched from the
        self.klines_data for that symbol
        """
        zigzag_df = zigzag.calculate(klines_data)

        msbs_df = msb_identifier.find_all_matches(
            zigzag_df["structure"].tolist(),
            zigzag_df["kline_index"].tolist(),
            zigzag_df["pivot_value"].tolist(),
            zigzag_df["pivot_formation_index"].tolist(),
        )

        block_manager.add_blocks(msbs_df, zigzag_df, klines_data)
        block_manager.update_block_end_times(klines_data)

