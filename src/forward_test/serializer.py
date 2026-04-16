"""
This module contains functions to serialize and store ForwardTest data in files, used
for charting.
"""

from datetime import datetime
from ormsgpack import packb, OPT_SERIALIZE_NUMPY
import logging

from src.logic.blocks.block import Block
from src.data_provider import LiveKLinesData
from src.config import Config

config = Config()
logger = logging.getLogger("[FTChartSerializer]")


class FTChartSerializer:
    def __init__(self, chart_data_dir: str = "data/chart"):
        self._chart_data_dir = chart_data_dir
        self._latest_packed_data: dict[str, bytes] = {}
        self._last_write_time: datetime | None = None

    def _update_last_write_time(self):
        self._last_write_time = datetime.now()

    def _serialize_for_symbol(
        self, klines_data: LiveKLinesData, blocks_list: list[Block]
    ):
        """
        Takes KLinesData and blocks list for a symbol and serializes it to a dict.
        """
        chart_data = {"blocks": [], "klines": None}
        chart_data["klines"] = klines_data.get_dict_format()

        for block in blocks_list:
            serialized_block_data = {
                "type": block.block_type,
                "direction": block.direction,
                "start_index": block.start_index,
                "start_time": block.start_time.value if block.start_time else None,
                "end_index": block.end_index,
                "end_time": block.end_time.value if block.end_time else None,
                "high": block.high,
                "low": block.low,
            }

            chart_data["blocks"].append(serialized_block_data)

        return chart_data

    def _pack_serialized_data(
        self,
        agg_klines_data: dict[str, LiveKLinesData],
        agg_blocks_list: dict[str, list[Block]],
    ):
        """
        Serializes the KLinesData and blocks list of the forward test using msgpack (compressed binary)
        and stores it as an attribute.

        Args:
            agg_klines_data: A symbol-separated dict of KLinesData.
            agg_blocks_list: A symbol-separated dict of list of Blocks (Not separated by direction)
        """
        for symbol in agg_klines_data.keys():
            serialized_ft_data = self._serialize_for_symbol(
                agg_klines_data[symbol], agg_blocks_list[symbol]
            )
            self._latest_packed_data[symbol] = packb(
                serialized_ft_data, option=OPT_SERIALIZE_NUMPY
            )

    def write(
        self,
        agg_klines_data: dict[str, LiveKLinesData],
        agg_blocks_list: dict[str, list[Block]],
    ):
        """
        msgpack-serializes the ForwardTest KLinesData and Blocks and writes them to a file for each symbol, if enough
        time has passed since the last write operation.
        """
        now = datetime.now()
        if self._last_write_time is not None and (
            now - self._last_write_time
        ).total_seconds() < int(config.get("calc_interval")):
            return

        self._pack_serialized_data(agg_klines_data, agg_blocks_list)

        try:
            for symbol, packed_data in self._latest_packed_data.items():
                filepath = self._chart_data_dir + f"/{symbol}.pack"
                with open(filepath, "wb") as fs:
                    fs.write(packed_data)
        except Exception as e:
            logger.error(f"Writing data to file failed: {e}")

        logger.debug("Wrote serialized data to files.")

        self._update_last_write_time()
