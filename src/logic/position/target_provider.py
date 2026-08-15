"""
This module will contain small factories which return a list of targets using a method given by a string.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
from numpy import float64, array, ones
from numpy.typing import NDArray

from src.config import Config

if TYPE_CHECKING:
    from src.logic import Position

config = Config()


@dataclass(frozen=True)
class TargetPlan:
    prices: NDArray[float64]
    quantity_weights: NDArray[float64]


class TargetProvider:
    @staticmethod
    def get_target_plan(position: Position) -> TargetPlan:
        method = config.target_setup_function
        return getattr(TargetProvider, method)(position)

    @staticmethod
    def _build_target_plan(
        targets: NDArray[float64], quantity_weights: NDArray[float64] | None = None
    ) -> TargetPlan:
        if quantity_weights is None:
            quantity_weights = ones(len(targets), dtype=float64)

        return TargetPlan(prices=targets, quantity_weights=quantity_weights)

    @staticmethod
    def _get_evenly_spaced_targets(
        position: Position,
        base_height: float,
        n_targets: int = 4,
    ) -> NDArray[float64]:
        target_coeff = config.target_coeff

        if position.type == "long":
            return array(
                [
                    position.entry + i * base_height * target_coeff
                    for i in range(1, n_targets + 1)
                ]
            )

        return array(
            [
                position.entry - i * base_height * target_coeff
                for i in range(1, n_targets + 1)
            ]
        )

    @staticmethod
    def _first_target_half_rest_even_weights(n_targets: int) -> NDArray[float64]:
        if n_targets <= 0:
            raise ValueError("Target count must be positive.")

        if n_targets == 1:
            return ones(1, dtype=float64)

        return array([n_targets - 1, *([1] * (n_targets - 1))], dtype=float64)

    @staticmethod
    def default(position: Position) -> TargetPlan:
        """
        4 evenly spaced targets. Spaced by 1 block height * target_coeff between them.
        """
        base_height = position.base_block.height
        targets = TargetProvider._get_evenly_spaced_targets(position, base_height)

        return TargetProvider._build_target_plan(targets)

    @staticmethod
    def default_t1_half_rest_even(position: Position) -> TargetPlan:
        """
        4 evenly spaced targets with 50% of quantity taken at target 1 and the
        remainder split evenly across the rest.
        """
        base_height = position.base_block.height
        targets = TargetProvider._get_evenly_spaced_targets(position, base_height)
        quantity_weights = TargetProvider._first_target_half_rest_even_weights(
            len(targets)
        )

        return TargetProvider._build_target_plan(targets, quantity_weights)

    @staticmethod
    def small_blocks_refined(
        position: Position,
    ) -> TargetPlan:
        """
        4 evenly spaced targets for blocks between 2 and 3% height%. Blocks between 0 and 2%
        don't use the base block height, and instead use 1% of the price as the base height.
        """
        height_percentage = position.base_block.height_percentage

        # In small blocks (0-2%) the base height is ignored and replaced by 1% of the
        #  average base block price.
        if 0 <= height_percentage < 2:
            base_height = (
                0.01 * (position.base_block.high + position.base_block.low) / 2
            )

        # In other cases the base_block height is used as the foundation for building targets.
        else:
            base_height = position.base_block.height

        targets = TargetProvider._get_evenly_spaced_targets(position, base_height)

        return TargetProvider._build_target_plan(targets)

    @staticmethod
    def small_blocks_refined_t1_half_rest_even(
        position: Position,
    ) -> TargetPlan:
        """
        4 evenly spaced targets with the same spacing logic as
        small_blocks_refined(), but with 50% taken at target 1 and the remainder
        split evenly across later targets.
        """
        target_plan = TargetProvider.small_blocks_refined(position)
        quantity_weights = TargetProvider._first_target_half_rest_even_weights(
            len(target_plan.prices)
        )

        return TargetProvider._build_target_plan(
            target_plan.prices, quantity_weights
        )
