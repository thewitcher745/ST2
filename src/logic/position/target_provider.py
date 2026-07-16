"""
This module will contain small factories which return a list of targets using a method given by a string.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from numpy import float64, array
from numpy.typing import NDArray

from src.config import Config

if TYPE_CHECKING:
    from src.logic import Position

config = Config()


class TargetProvider:
    @staticmethod
    def get_targets(position: Position) -> NDArray[float64]:
        method = config.target_setup_function
        return getattr(TargetProvider, method)(position)

    @staticmethod
    def default(position: Position) -> NDArray[float64]:
        """
        4 evenly spaced targets. Spaced by 1 block height * target_coeff between them.
        """
        base_height = position.base_block.height
        target_coeff = config.target_coeff

        if position.type == "long":
            targets = array(
                [
                    position.entry + 1 * base_height * target_coeff,
                    position.entry + 2 * base_height * target_coeff,
                    position.entry + 3 * base_height * target_coeff,
                    position.entry + 4 * base_height * target_coeff,
                ]
            )

        else:
            targets = array(
                [
                    position.entry - 1 * base_height * target_coeff,
                    position.entry - 2 * base_height * target_coeff,
                    position.entry - 3 * base_height * target_coeff,
                    position.entry - 4 * base_height * target_coeff,
                ]
            )

        return targets

    @staticmethod
    def small_blocks_refined(
        position: Position,
    ) -> NDArray[float64]:
        """
        4 evenly spaced targets for blocks between 2 and 3% height%. Blocks between 0 and 2%
        don't use the base block height, and instead use 1% of the price as the base height.
        """
        height_percentage = position.base_block.height_percentage
        target_coeff = config.target_coeff

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
            targets = array(
                [
                    position.entry + 1 * base_height * target_coeff,
                    position.entry + 2 * base_height * target_coeff,
                    position.entry + 3 * base_height * target_coeff,
                    position.entry + 4 * base_height * target_coeff,
                ]
            )

        else:
            targets = array(
                [
                    position.entry - 1 * base_height * target_coeff,
                    position.entry - 2 * base_height * target_coeff,
                    position.entry - 3 * base_height * target_coeff,
                    position.entry - 4 * base_height * target_coeff,
                ]
            )

        return targets

    @staticmethod
    def small_blocks_refined_05_percent(
        position: Position,
    ) -> NDArray[float64]:
        """
        4 evenly spaced targets for blocks between 2 and 3% height%. Blocks between 0 and 2%
        don't use the base block height, and instead use 0.5% of the price as the base height.
        """
        height_percentage = position.base_block.height_percentage
        target_coeff = config.target_coeff

        # In small blocks (0-2%) the base height is ignored and replaced by 1% of the
        #  average base block price.
        if 0 <= height_percentage < 2:
            base_height = (
                0.005 * (position.base_block.high + position.base_block.low) / 2
            )

        # In other cases the base_block height is used as the foundation for building targets.
        else:
            base_height = position.base_block.height

        if position.type == "long":
            targets = array(
                [
                    position.entry + 1 * base_height * target_coeff,
                    position.entry + 2 * base_height * target_coeff,
                    position.entry + 3 * base_height * target_coeff,
                    position.entry + 4 * base_height * target_coeff,
                ]
            )

        else:
            targets = array(
                [
                    position.entry - 1 * base_height * target_coeff,
                    position.entry - 2 * base_height * target_coeff,
                    position.entry - 3 * base_height * target_coeff,
                    position.entry - 4 * base_height * target_coeff,
                ]
            )

        return targets
