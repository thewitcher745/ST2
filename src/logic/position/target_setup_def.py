"""
This module will contain small factories which modify a Position object's stoploss and targets, and return nothing.
"""

from numpy import array

from ...config import Config

config = Config()


def default(position):
    base_height = position.base_block.height
    target_coeff = float(config.target_coeff)
    stop_coeff = float(config.stop_coeff)

    if position.type == "long":
        targets = array(
            [
                position.entry + 1 * base_height * target_coeff,
                position.entry + 2 * base_height * target_coeff,
                position.entry + 3 * base_height * target_coeff,
                position.entry + 4 * base_height * target_coeff,
            ]
        )
        stoploss = position.entry - base_height * stop_coeff

    else:
        targets = array(
            [
                position.entry - 1 * base_height * target_coeff,
                position.entry - 2 * base_height * target_coeff,
                position.entry - 3 * base_height * target_coeff,
                position.entry - 4 * base_height * target_coeff,
            ]
        )
        stoploss = position.entry + base_height * stop_coeff

    position.set_targets(targets)
    position.set_stoploss(stoploss)
