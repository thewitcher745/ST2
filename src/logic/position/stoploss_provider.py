"""
This module will contain small factories which return a list of stoplosses using a method given by a string.
The methods can be configured to return dynamic or trailing stoplosses after each target. The outputs are ndarrays,
the size of the target array, which is one stoploss for each target except the last, plus ont for the entry. The
output shows where the stoploss is after each target has been hit.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from numpy import float64, array
from numpy.typing import NDArray

from src.config import Config

if TYPE_CHECKING:
    from src.logic import Position

config = Config()


class StoplossProvider:
    @staticmethod
    def get_stoplosses(position: Position) -> NDArray[float64]:
        method = config.stoploss_setup_function
        return getattr(StoplossProvider, method)(position)

    @staticmethod
    def default(position: Position) -> NDArray[float64]:
        """
        No trailing stoploss configuration. Fixed stoploss all the way.
        """
        base_height = position.base_block.height
        stoploss_coeff = config.stoploss_coeff
        # Length is number of targets - 1, plus one for the entry, so length of targets
        sl_array_length = len(position.targets)

        # sl_0 is the stoploss as calculated from the block height and stoploss_coeff, no
        # other modification applied.
        if position.type == "long":
            sl_0 = position.entry - stoploss_coeff * base_height
        else:
            sl_0 = position.entry + stoploss_coeff * base_height

        stoplosses = array([sl_0] * sl_array_length)

        return stoplosses

    @staticmethod
    def trailing_breakeven_t1(position: Position) -> NDArray[float64]:
        """
        No trailing stoploss configuration. Fixed stoploss all the way.
        """
        base_height = position.base_block.height
        stoploss_coeff = config.stoploss_coeff
        # Length is number of targets - 1, plus one for the entry, so length of targets
        sl_array_length = len(position.targets)

        # sl_0 is the stoploss as calculated from the block height and stoploss_coeff, no
        # other modification applied.
        if position.type == "long":
            sl_0 = position.entry - stoploss_coeff * base_height
        else:
            sl_0 = position.entry + stoploss_coeff * base_height

        stoplosses = array([sl_0] + [position.entry] * (sl_array_length - 1))

        return stoplosses

    @staticmethod
    def small_blocks_refined_no_trailing(
        position: Position,
    ) -> NDArray[float64]:
        """
        Blocks between 0 and 2% don't use the base block height for the stoploss, and instead
        use 1% of the price as the base height.
        """
        height_percentage = position.base_block.height_percentage
        stoploss_coeff = config.stoploss_coeff

        sl_array_length = len(position.targets)

        # In small blocks (0-2%) the base height is ignored and replaced by 1% of the
        #  average base block price.
        if 0 <= height_percentage < 2:
            base_height = (
                0.01 * (position.base_block.high + position.base_block.low) / 2
            )

        # In other cases the base_block height is used as the foundation for building targets.
        else:
            base_height = position.base_block.height

        if position.type == "long":
            sl_0 = position.entry - stoploss_coeff * base_height
        else:
            sl_0 = position.entry + stoploss_coeff * base_height

        stoplosses = array([sl_0] * sl_array_length)

        return stoplosses

    @staticmethod
    def small_blocks_refined_trailing_breakeven_t1(
        position: Position,
    ) -> NDArray[float64]:
        """
        Blocks between 0 and 2% don't use the base block height for the stoploss, and instead
        use 1% of the price as the base height. This function also utilizes trailing-breakeven 
        stoploss setup, moving the stoploss to the entry after the first target is hit.
        """
        height_percentage = position.base_block.height_percentage
        stoploss_coeff = config.stoploss_coeff

        sl_array_length = len(position.targets)

        # In small blocks (0-2%) the base height is ignored and replaced by 1% of the
        #  average base block price.
        if 0 <= height_percentage < 2:
            base_height = (
                0.01 * (position.base_block.high + position.base_block.low) / 2
            )

        # In other cases the base_block height is used as the foundation for building targets.
        else:
            base_height = position.base_block.height

        if position.type == "long":
            sl_0 = position.entry - stoploss_coeff * base_height
        else:
            sl_0 = position.entry + stoploss_coeff * base_height

        stoplosses = array([sl_0] + [position.entry] * (sl_array_length - 1))

        return stoplosses
