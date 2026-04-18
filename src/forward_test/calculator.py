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
        self._last_calc_time: datetime | None = None

    def _update_last_calc_time(self):
        self._last_calc_time = datetime.now()

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
        now = datetime.now()
        if self._last_calc_time is not None and (
            now - self._last_calc_time
        ).total_seconds() < int(config.get("calc_interval")):
            return

        zigzag_df = zigzag.calculate(klines_data)

        msbs_df = msb_identifier.find_all_matches(
            zigzag_df["structure"].tolist(),
            zigzag_df["kline_index"].tolist(),
            zigzag_df["pivot_value"].tolist(),
            zigzag_df["pivot_formation_index"].tolist(),
        )

        block_manager.update_blocks(msbs_df, zigzag_df, klines_data)
        block_manager.update_block_end_times(klines_data)

        position_manager.update_positions(blocks=block_manager.all_active_blocks_aslist)
        position_manager.simulate_all_positions(klines_data)

        self._update_last_calc_time()
