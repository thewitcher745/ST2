from datetime import datetime
import logging
from pandas import concat, DataFrame

from src.logger.logger_config import configure_logging
from src.config import Config
from src.data_provider import KLinesData, LocalDataProvider
from src.logic import MSBIdentifier, Zigzag, BlockManager, PositionManager

config = Config()
logger = logging.getLogger("[BacktestExecutor]")


class BacktestExecutor:
    """
    Initiates a backtest executor object. Use BacktestExecutor.execute() to
    execute a backtest with the current config on a list of symbols, between a start
    and an end time.
    """

    def __init__(self):
        self._zigzag = Zigzag()
        self._data_provider = LocalDataProvider()
        self._msb_identifier = MSBIdentifier()
        self._block_manager = BlockManager()
        self._position_manager = PositionManager()

    def execute(
        self,
        symbols: list[str],
        start_time: datetime,
        end_time: datetime,
        run_id: str = "default",
    ) -> DataFrame:
        """
        Run the backtest and return the dataframe of positions from it.
        """
        configure_logging(is_backtest=True, run_id=run_id)

        positions = []
        for symbol in symbols:
            self._block_manager.reset_blocks()
            self._position_manager.reset_positions()
            try:
                klines_df = self._data_provider.get_klines(
                    symbol, config.timeframe, start_time, end_time
                )

                klines_data = KLinesData(klines_df)

                # logger.debug(
                #     f"Fetched {klines_data.length} candles for symbol {symbol}"
                # )

            except Exception as e:
                logger.error(f"Failed to get data for {symbol}: {e}")
                logger.error("Skipping symbol...")
                continue

            try:
                zigzag_df = self._zigzag.calculate(klines_data)

                msbs_df = self._msb_identifier.find_all_matches(
                    zigzag_df["pivot_type"].tolist(),
                    zigzag_df["kline_index"].tolist(),
                    zigzag_df["pivot_value"].tolist(),
                    zigzag_df["pivot_formation_index"].tolist(),
                )
                
                self._block_manager.update_blocks(msbs_df, zigzag_df, klines_data)
                self._block_manager.update_block_end_times(klines_data)

                self._position_manager.simulate_and_generate_positions(
                    self._block_manager.all_blocks_aslist, klines_data
                )

            except Exception as e:
                logger.error(f"Failed to calculate positions for symbol {symbol}: {e}")
                logger.error("Skipping symbol...")
                continue

            positions.append(self._position_manager.to_dataframe())
            # logger.debug(
            #     f"Added {len(self._position_manager.positions_aslist)} positions for symbol {symbol}"
            # )

        return concat(positions, ignore_index=True) if positions else DataFrame()
