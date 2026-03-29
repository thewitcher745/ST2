"""
This module will contain small factories which return a list of stoplosses using a method given by a string.
The methods can be configured to return dynamic or trailing stoplosses after each target. The outputs are ndarrays,
the size of the target array, which is one stoploss for each target except the last, plus ont for the entry. The
output shows where the stoploss is after each target has been hit.
"""

from numpy import float64, array
from numpy.typing import NDArray

from ...config import Config

config = Config()


class StoplossProvider:
    @staticmethod
    def get_stoplosses(position) -> NDArray[float64]:
        method = config.stoploss_setup_function
        return getattr(StoplossProvider, method)(position)

    @staticmethod
    def default(position) -> NDArray[float64]:
        """
        No trailing stoploss configuration. Fixed stoploss all the way.
        """
        base_height = position.base_block.height
        stoploss_coeff = float(config.stoploss_coeff)
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
    def trailing_breakeven_t1(position) -> NDArray[float64]:
        """
        No trailing stoploss configuration. Fixed stoploss all the way.
        """
        base_height = position.base_block.height
        stoploss_coeff = float(config.stoploss_coeff)
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
