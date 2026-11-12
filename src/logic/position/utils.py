"""
Random, small utilities and constants.
"""

from __future__ import annotations

from math import isfinite
from typing import TYPE_CHECKING

from src.config import Config

if TYPE_CHECKING:
    from .position import Position


def get_atr_exit_distance(position: Position) -> float:
    """Shared target/stop distance for the paired ATR methods at 1:1 reward/risk."""
    config = Config()
    if config.target_setup_function != "atr" or config.stoploss_setup_function != "atr":
        raise ValueError(
            "ATR exits require both target and stoploss setup functions to be 'atr'."
        )
    coeff = config.atr_exit_coeff
    if not isfinite(coeff) or coeff <= 0:
        raise ValueError("atr_exit_coeff must be finite and positive.")
    atr = position.base_block.prior_atr
    if atr is None or not isfinite(atr) or atr <= 0:
        raise ValueError("ATR exits require 14 valid candles before the base candle.")
    distance = atr * coeff
    if not isfinite(distance) or distance <= 0:
        raise ValueError("ATR exit distance must be finite and positive.")
    return distance


# This dict defines which direction each level is. The correct direction of the level
# is then determined by subtracting them. If the sign of deducing the first event from the
# second is negative, that means the order should be reversed.
change_directions_dict = {
    "long": {"target": 1, "entry": 0, "stop": -1},
    "short": {"target": -1, "entry": 0, "stop": 1},
}
