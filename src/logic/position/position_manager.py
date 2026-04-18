from pandas import DataFrame

from src.data_provider import KLinesData
from .position import Position
from ..blocks.block import Block
from ..backtest import PositionSimulator


class PositionManager:
    def __init__(self):
        self.positions: dict[str, list[Position]] = {"long": [], "short": []}

    def update_positions(self, blocks: list[Block]):
        """
        Updates the list of positions from a given list of blocks, direction-agnostic.
        """
        positions: dict[str, list[Position]] = {"long": [], "short": []}
        for block in blocks:
            type = "long" if block.direction == "bullish" else "short"
            positions[type].append(Position(block))

        self.positions = positions

    @property
    def positions_aslist(self) -> list[Position]:
        """Takes a long/hort separated dict of positions and returns a combined list."""
        return [
            position for position in self.positions["long"] + self.positions["short"]
        ]

    def simulate_all_positions(self, klines_data: KLinesData):
        """
        Simulates the entry, targets and stoplosses of all positions and sets their net and percent
        profits.
        """
        for type in ["short", "long"]:
            for position in self.positions[type]:
                PositionSimulator.simulate(position, klines_data)

    def to_dataframe(self) -> DataFrame:
        return DataFrame(
            [
                position.to_dict()
                for position in self.positions["long"] + self.positions["short"]
            ]
        )
