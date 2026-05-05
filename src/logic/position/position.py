from __future__ import annotations
from typing import Literal, Optional
from numpy import float64, array, int64
from numpy.typing import NDArray
from pandas import Timestamp

from .stoploss_provider import StoplossProvider
from .target_provider import TargetProvider
from ..blocks.block import Block
from src.config import Config
from src.utils import isoformat_none_or_timestamp

config = Config()


class Position:
    def __init__(self, base_block: Block, bounce_id: int = 0):
        self.base_block = base_block
        self.start_time = base_block.start_time
        self.type: Literal["short", "long"] = "long"

        if base_block.direction == "bullish":
            self.entry = base_block.high
        else:
            self.type = "short"
            self.entry = base_block.low

        self.stoplosses: NDArray[float64] = array([])
        self.targets: NDArray[float64] = array([])

        self.entry_time: Optional[Timestamp] = None
        self.entry_index: Optional[int] = None
        self.target_times: list[Timestamp] = []
        self.target_indices: NDArray[int64] = array([])
        self.stop_time: Optional[Timestamp] = None
        self.stop_index: Optional[int] = None
        self.stop_price: Optional[float] = None
        self.exit_time: Optional[Timestamp] = None
        self.exit_type: Optional[str] = None

        self.entered: bool = False
        self.net_profit: float = 0
        self.percent_profit: float = 0
        self.highest_target: int = 0
        self.full_target: bool = False
        # Indicates which bounce of the base block this position belongs to.
        self.bounce_id = bounce_id

        # This ID is only used to compare positions
        self.id = self.base_block.id + f"_{self.bounce_id}"

        # Add the position to its base block's positions list
        self.base_block.positions.append(self)

        self.setup_targets()
        self.setup_stoplosses()

    def __eq__(self, other) -> bool:
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def setup_targets(self):
        """
        This method uses an external module to set up the targets.
        """
        targets = TargetProvider.get_targets(self)
        self.targets = targets

    def setup_stoplosses(self):
        """
        This method uses an external module to set up the stoplosses, one per target
        """
        stoplosses = StoplossProvider.get_stoplosses(self)
        self.stoplosses = stoplosses

    def to_dict(self) -> dict:
        if self.exit_type == "FULL_TARGET":
            exit_time = self.target_times[-1]
        else:
            exit_time = self.stop_time
        return {
            "base_block_id": self.base_block.id,
            "type": self.type,
            "entered": self.entered,
            "exit_type": self.exit_type,
            "base_block_height_percentage": self.base_block.height_percentage,
            "highest_target": self.highest_target,
            "net_profit": self.net_profit,
            "percent_profit": self.percent_profit,
            "full_target": self.full_target,
            "entry": self.entry,
            "targets": self.targets,
            "stoplosses": self.stoplosses,
            "entry_time": isoformat_none_or_timestamp(self.entry_time),
            "exit_time": isoformat_none_or_timestamp(exit_time),
            "target_times": [
                isoformat_none_or_timestamp(target_time)
                for target_time in self.target_times
            ],
            "stop_time": isoformat_none_or_timestamp(self.stop_time),
            "stop_price": self.stop_price,
        }
