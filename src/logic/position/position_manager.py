from pandas import DataFrame

from src.data_provider import KLinesData
from .position import Position
from ..blocks.block import Block
from ..backtest import PositionSimulator


class PositionManager:
    def __init__(self):
        self.all_positions: dict[str, list[Position]] = {"long": [], "short": []}
        self.active_positions: dict[str, list[Position]] = {"long": [], "short": []}

    def update_positions(self, blocks: list[Block], active=False):
        """
        Updates the list of positions from a given list of blocks, direction-agnostic.
        """
        all_positions: dict[str, list[Position]] = {"long": [], "short": []}
        active_positions: dict[str, list[Position]] = {"long": [], "short": []}
        for block in blocks:
            type = "long" if block.direction == "bullish" else "short"
            if active:
                active_positions[type].append(Position(block))
            else:
                all_positions[type].append(Position(block))

        if active:
            self.active_positions = active_positions
        else:
            self.all_positions = all_positions

    @property
    def all_active_positions(self) -> list[Position]:
        """Takes a long/hort separated dict of positions and returns a combined dict."""
        return [
            position
            for position in self.active_positions["long"]
            + self.active_positions["short"]
        ]

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
