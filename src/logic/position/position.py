from numpy import ndarray, array, where
import pandas as pd

from ...data_provider import KLinesData
from ..blocks.block import Block
from .target_setup_dir import TargetSetupDir
from ...config import Config

config = Config()


class Position:
    def __init__(self, base_block: Block):
        self.base_block = base_block
        self.start_time = base_block.start_time

        if base_block.direction == "bullish":
            self.type = "long"
            self.entry = base_block.high

        else:
            self.type = "short"
            self.entry = base_block.low

        self.stoploss: float = None
        self.targets: ndarray[float] = array([])

        self.entry_time: pd.Timestamp = None
        self.target_times: list[pd.timestamp] = []
        self.stop_time: pd.Timestamp = None
        self.exit_time: pd.Timestamp = None

        self.status = "NOT_ENTERED"
        self.net_profit: float = 0
        self.percent_profit: float = 0
        self.highest_target: int = 0
        self.full_target: bool = False

        self.setup_stop_targets()

    def set_targets(self, targets: ndarray[float]):
        self.targets = targets

    def set_stoploss(self, stoploss: float):
        self.stoploss = stoploss

    def setup_stop_targets(self):
        """
        This method uses an external module to set up the stoploss and the targets.
        """
        setup_function = TargetSetupDir.setups[config.target_setup_function]
        setup_function(self)

    def calc_events(self, klines_data: KLinesData):
        """
        The event list re-tells what happened to the position and when.
        """
        # Filter the candles of klines_df from the start of the block to its end. If no
        # end is registered, go all the way to the end candle of the data.
        index_offset = self.base_block.start_index + 1

        if self.base_block.end_index:
            lows_within_block = klines_data.low[
                index_offset : self.base_block.end_index + 1
            ]
            highs_within_block = klines_data.high[
                index_offset : self.base_block.end_index + 1
            ]
        else:
            lows_within_block = klines_data.low[self.base_block.start_index :]
            highs_within_block = klines_data.high[self.base_block.start_index :]

        # Variables declared for brevity of the code, so less nesting is needed
        if self.type == "long":
            entry_check_condition = lows_within_block <= self.entry
            stoploss_check_condition = lows_within_block <= self.stoploss
            stoploss_registry_array = highs_within_block
        else:
            entry_check_condition = highs_within_block >= self.entry
            stoploss_check_condition = highs_within_block >= self.stoploss
            stoploss_registry_array = lows_within_block

        # Find the first entry event.
        entry_candles = where(entry_check_condition)[0]
        if len(entry_candles) > 0:
            self.status = "ENTERED"
            # +1 because the candle starting the block should not register, as the algo
            # probably can't react fast enough.
            first_entry_index = entry_candles[0] + index_offset
            first_stoploss_index = None
            # Find the first stoploss event.
            stoploss_candles = where(stoploss_check_condition)[0]
            if len(stoploss_candles) > 0:
                # +1 because the candle starting the block should not register, as the algo
                # probably can't react fast enough.
                first_stoploss_index = stoploss_candles[0] + index_offset

            # The first entry candle is ALWAYS earlier or at least equal to the first
            # stoploss. Because in the conditions being checked above, the stoploss
            # is always below the entry, so any candle with a low below the stoploss is
            # also below the entry.

            # Register the entry time
            self.entry_time = klines_data.time[first_entry_index]

            # Register the stoploss time, if there is one.
            if first_stoploss_index:
                self.stop_time = klines_data.time[first_stoploss_index]

                # The targets will be checked for in the candles between the entry and the
                # stoploss indices. If no stoploss is registered, the entire span of the
                # start index to the end of the klines_data is checked.

                check_window_extrema = stoploss_registry_array[
                    first_entry_index - index_offset : first_stoploss_index
                    - index_offset
                ]
            else:
                check_window_extrema = stoploss_registry_array[
                    first_entry_index - index_offset :
                ]
            check_window_offset = first_entry_index
            # The check_window variables are the lows and highs of the candles that need
            # to be checked for target hits, in order. The target hit time for each target
            # is then registered for later review. check_window_offset is the value that
            # we need to add to any locally-indexed indices to get the global klines_df
            # index for that event.

            # Since each target necessarily happens after (or on the same candle) as the
            # previous target, there should be a dynamic offset that keeps track of the
            # highest target hit before the current one being processed. Initially this is
            # at check_window_offset, which means we are at the first candle of the check
            # window. If a target is found, the current offset is changed by the index of the
            # candle of the current target, if found (locally indexed).
            current_offset = check_window_offset
            self.highest_target = 0
            for target in self.targets:
                if self.type == "long":
                    current_target_hitting_candles = where(
                        check_window_extrema >= target
                    )[0]
                else:
                    current_target_hitting_candles = where(
                        check_window_extrema <= target
                    )[0]

                if len(current_target_hitting_candles) > 0:
                    first_candle_to_hit_target_index = current_target_hitting_candles[0]

                    # If the first candle to hit target is the same as the entry candle, aka 0
                    # in the local index, we need to check the candle color before registering a
                    # target. In long positions, if the candle is bullish, that means the entry
                    # was (probably) achieved before the target, and vice versa. If in a long
                    # position the candle to achieve both entry and target is bearish, we only
                    # register the entry and not the target.
                    if first_candle_to_hit_target_index == 0:
                        # Find the color of the candle
                        candle_index = first_candle_to_hit_target_index + current_offset
                        candle_color = (
                            "green"
                            if klines_data.close[candle_index]
                            > klines_data.open[candle_index]
                            else "red"
                        )

                        if candle_color == "green" and self.type == "long":
                            pass
                        elif candle_color == "red" and self.type == "short":
                            pass

                        # If an opposite direction candle gives both an entry and a target, check if any other candles
                        # after it achive a target. If no such candles exist, that means no other targets will be achieved.
                        else:
                            if len(current_target_hitting_candles) > 1:
                                first_candle_to_hit_target_index = (
                                    current_target_hitting_candles[1]
                                )
                            else:
                                break

                    self.highest_target += 1

                    target_hit_time = klines_data.time[
                        first_candle_to_hit_target_index + current_offset
                    ]
                    self.target_times.append(target_hit_time)
                    current_offset += first_candle_to_hit_target_index
                    check_window_extrema = check_window_extrema[
                        first_candle_to_hit_target_index:
                    ]

                # If a target is not hit by the end of the check window, that means that no
                # target after it will be hit either, so we can safely break without checking
                # the rest of the targets.
                else:
                    break

            # Now we aggregate all the results and close out the position safely.
            if self.highest_target > 0:
                self.status = f"TARGET_{self.highest_target}"

                # If all targets are achieved, set the stop time to None and full_target to True
                if self.highest_target == len(self.targets):
                    self.full_target = True
                    self.stop_time = None

            else:
                self.status = "STOPLOSS"

    def calc_profit(self):
        """
        This method calculates the net and percent profit of the position based on its entry, targets and stoploss.
        """
        total_margin_per_trade = float(config.usdt_per_trade) * float(config.leverage)
        n_targets = len(self.targets)
        qty = total_margin_per_trade / self.entry
        if self.status != "NOT_ENTERED":
            if self.type == "long":
                loss_from_entry = total_margin_per_trade
                qty_per_target = qty / n_targets
                qty_stoploss = sum([qty_per_target] * (n_targets - self.highest_target))
                targets_qty_array = [qty_per_target] * (self.highest_target) + [0] * (
                    n_targets - self.highest_target
                )
                gain_from_targets = sum(array(targets_qty_array) * self.targets)
                gain_from_stoploss = qty_stoploss * self.stoploss

                self.net_profit = (
                    gain_from_targets + gain_from_stoploss - loss_from_entry
                )

            else:
                gain_from_entry = total_margin_per_trade
                qty_per_target = qty / n_targets
                qty_stoploss = sum([qty_per_target] * (n_targets - self.highest_target))
                targets_qty_array = [qty_per_target] * (self.highest_target) + [0] * (
                    n_targets - self.highest_target
                )
                loss_from_targets = sum(array(targets_qty_array) * self.targets)
                loss_from_stoploss = qty_stoploss * self.stoploss

                self.net_profit = (
                    gain_from_entry - loss_from_targets - loss_from_stoploss
                )

            self.percent_profit = self.net_profit / float(config.usdt_per_trade) * 100

    def to_dict(self) -> dict:
        return {
            "base_block_id": self.base_block.id,
            "type": self.type,
            "status": self.status,
            "base_block_height_percentage": self.base_block.height_percentage,
            "highest_target": self.highest_target,
            "net_profit": self.net_profit,
            "percent_profit": self.percent_profit,
            "full_target": self.full_target,
            "entry": self.entry,
            "targets": self.targets,
            "stoploss": self.stoploss,
            "entry_time": self.entry_time,
            "target_times": self.target_times,
            "stop_time": self.stop_time,
        }
