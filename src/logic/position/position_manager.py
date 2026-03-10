from pandas import DataFrame

from ...data_provider import KLinesData
from .position import Position
from ..blocks.block import Block


class PositionManager:
    def __init__(self):
        self.all_positions: dict[str, list[Position]] = {"long": [], "short": []}

    def add_positions(self, blocks: list[Block]):
        for block in blocks:
            type = "long" if block.direction == "bullish" else "short"
            self.all_positions[type].append(Position(block))

    def calc_all_positions_events(self, klines_data: KLinesData):
        for type in ["long", "short"]:
            for position in self.all_positions[type]:
                position.calc_events(klines_data)

    def to_dataframe(self) -> DataFrame:
        return DataFrame(
            [
                position.to_dict()
                for position in self.all_positions["long"] + self.all_positions["short"]
            ]
        )
