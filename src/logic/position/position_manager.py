from pandas import DataFrame

from src.data_provider import KLinesData
from .position import Position
from ..blocks.block import Block
from ..backtest import PositionSimulator
from src.config import Config

config = Config()


class PositionManager:
    def __init__(self):
        self.positions: dict[str, list[Position]] = {"long": [], "short": []}

    @property
    def positions_aslist(self) -> list[Position]:
        """Takes a long/hort separated dict of positions and returns a combined list."""
        return [
            position for position in self.positions["long"] + self.positions["short"]
        ]

    def simulate_and_generate_positions(
        self, blocks: list[Block], klines_data: KLinesData
    ):
        """
        Simulates all positions and generates new positions for each bounce.
        """
        self.positions = {"long": [], "short": []}
        for block in blocks:
            type = "long" if block.direction == "bullish" else "short"
            position = Position(block)
            search_start_index = position.base_block.start_index + 1

            # Simulate until the block can't have any more bounces
            while True:
                self.positions[type].append(position)
                PositionSimulator.simulate(position, klines_data, search_start_index)

                # Check bounce conditions
                if position.highest_target < config.bounce_target_threshold:
                    break
                if position.entered and position.exit_type == "STOPLOSS_0":
                    break
                if position.base_block.bounces >= config.max_bounces:
                    break

                # Create next bounce
                bounce_id = position.base_block.bounces
                next_position = Position(position.base_block, bounce_id=bounce_id)
                search_start_index = position.target_indices[
                    config.bounce_target_threshold - 1
                ]
                position = next_position  # Simulate the new position in next iteration

    def to_dataframe(self) -> DataFrame:
        return DataFrame(
            [
                position.to_dict()
                for position in self.positions["long"] + self.positions["short"]
            ]
        )
