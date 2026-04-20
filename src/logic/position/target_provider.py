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
