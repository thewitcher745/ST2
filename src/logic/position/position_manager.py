from pandas import DataFrame

from ...data_provider import KLinesData
from .position import Position
from ..blocks.block import Block
from .position_simulator import PositionSimulator


class PositionManager:
    def __init__(self):
        self.all_positions: dict[str, list[Position]] = {"long": [], "short": []}

    def add_positions(self, blocks: list[Block]):
        for block in blocks:
            type = "long" if block.direction == "bullish" else "short"
            self.all_positions[type].append(Position(block))

    def simulate_all_positions(self, klines_data: KLinesData):
        """
        Simulates the entry, targets and stoplosses of all positions and sets their net and percent
        profits.
        """
        for type in ["short", "long"]:
            for position in self.all_positions[type]:
                PositionSimulator.simulate(position, klines_data)

    def to_dataframe(self) -> DataFrame:
        return DataFrame(
            [
                position.to_dict()
                for position in self.all_positions["long"] + self.all_positions["short"]
            ]
        )
