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
        It is arbitrarily sized, and is empty at first. It is then populated
        with data showing what happened where. Each entry is a tuple, with the second
        element showing the index of the event, indexed on klines_df, and the first
        element showing what happened. Here is a list of event symbols:

            E: Entry event
            T + target_index: Target event
            S: Stoploss event

        A logical order of events is followed, for example a "target" element can only
        occur if an entry event has happened before it. Candles registering two events at
        the same time are judged using candle color logic, i.e. using the candle color
        to get a rough idea of what happened at the higher resolution chart.
        """
        # Filter the candles of klines_dffrom the start of the block to its end. If no
        # end is registered, go all the way to the end candle of the data.
        # The +1 is because the candle that ends the block can and usually is also the
        # candle that stops the position, so we should probably! consider it too.
        index_offset = self.base_block.start_index
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

        if self.type == "long":
            # Find the first entry event.
            entry_candles = where(lows_within_block <= self.entry)[0]
            if len(entry_candles) > 0:
                self.status = "ENTERED"
                # +1 because the candle starting the block should not register, as the algo
                # probably can't react fast enough.
                first_entry_index = entry_candles[0] + index_offset + 1
                first_stoploss_index = None
                # Find the first stoploss event.
                stoploss_candles = where(lows_within_block <= self.stoploss)[0]
                if len(stoploss_candles) > 0:
                    # +1 because the candle starting the block should not register, as the algo
                    # probably can't react fast enough.
                    first_stoploss_index = stoploss_candles[0] + index_offset + 1

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

                    check_window_highs = highs_within_block[
                        first_entry_index - index_offset : first_stoploss_index
                        - index_offset
                    ]
                else:
                    check_window_highs = highs_within_block[
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
                highest_target = 0
                for target in self.targets:
                    current_target_hitting_candles = where(check_window_highs > target)[
                        0
                    ]
                    if len(current_target_hitting_candles) > 0:
                        highest_target += 1
                        first_candle_to_hit_target_index = (
                            current_target_hitting_candles[0]
                        )
                        target_hit_time = klines_data.time[
                            first_candle_to_hit_target_index + current_offset
                        ]
                        self.target_times.append(target_hit_time)
                        current_offset += first_candle_to_hit_target_index
                        check_window_highs = check_window_highs[
                            first_candle_to_hit_target_index:
                        ]

                    # If a target is not hit by the end of the check window, that means that no
                    # target after it will be hit either, so we can safely break without checking
                    # the rest of the targets.
                    else:
                        break

                # Now we aggregate all the results and close out the position safely.
                if highest_target > 0:
                    self.status = f"TARGET_{highest_target}"
                else:
                    self.status = "STOPLOSS"

        else:
            entry_candles = where(highs_within_block >= self.entry)[0]
            if len(entry_candles) > 0:
                self.status = "ENTERED"
                first_entry_index = entry_candles[0] + index_offset + 1
                first_stoploss_index = None

                stoploss_candles = where(highs_within_block >= self.stoploss)[0]
                if len(stoploss_candles) > 0:
                    first_stoploss_index = stoploss_candles[0] + index_offset + 1

                self.entry_time = klines_data.time[first_entry_index]

                if first_stoploss_index:
                    self.stop_time = klines_data.time[first_stoploss_index]

                    check_window_lows = lows_within_block[
                        first_entry_index - index_offset : first_stoploss_index
                        - index_offset
                    ]
                else:
                    check_window_lows = lows_within_block[
                        first_entry_index - index_offset :
                    ]
                check_window_offset = first_entry_index

                current_offset = check_window_offset
                highest_target = 0
                for target in self.targets:
                    current_target_hitting_candles = where(check_window_lows < target)[
                        0
                    ]
                    if len(current_target_hitting_candles) > 0:
                        highest_target += 1
                        first_candle_to_hit_target_index = (
                            current_target_hitting_candles[0]
                        )
                        target_hit_time = klines_data.time[
                            first_candle_to_hit_target_index + current_offset
                        ]
                        self.target_times.append(target_hit_time)
                        current_offset += first_candle_to_hit_target_index
                        check_window_lows = check_window_lows[
                            first_candle_to_hit_target_index:
                        ]
                    else:
                        break

                if highest_target > 0:
                    self.status = f"TARGET_{highest_target}"
                else:
                    self.status = "STOPLOSS"


    def to_dict(self) -> dict:
        return {
            "base_block_id": self.base_block.id,
            "type": self.type,
            "status": self.status,
            "entry": self.entry,
            "targets": self.targets,
            "stoploss": self.stoploss,
            "entry_time": self.entry_time,
            "target_times": self.target_times,
            "stop_time": self.stop_time,
        }