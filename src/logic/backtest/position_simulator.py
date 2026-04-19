from __future__ import annotations
from typing import Literal, TYPE_CHECKING
from numpy import where, array
from numpy.typing import NDArray

from src.data_provider import KLinesData
from src.config import Config
from ..position.utils import change_directions_dict

if TYPE_CHECKING:
    from src.logic import Position

config = Config()


class PositionSimulator:
    @staticmethod
    def simulate(position: Position, klines_data: KLinesData):
        """Main orchestrator for the simulation logic."""
        PositionSimulator._calculate_temporal_events(position, klines_data)
        PositionSimulator._calculate_financial_outcome(position)

    @staticmethod
    def _calculate_temporal_events(pos: Position, klines_data: KLinesData):
        """Splits the event calculation into discrete steps."""
        # 1. Prepare data windows
        # Target lows and target highs are used to find the targets
        entry_lows, entry_highs, index_offset = PositionSimulator._get_window_slices(
            pos, klines_data
        )

        # 2. Find Entry index
        entry_index = PositionSimulator._find_entry(
            pos, entry_lows, entry_highs, index_offset
        )

        if entry_index is None:
            return

        pos.entered = True
        pos.entry_time = klines_data.time[entry_index]
        pos.entry_index = entry_index

        # 3. Process Targets
        PositionSimulator._process_targets(pos, klines_data, entry_index)

        # 4. Form stoploss check windows
        stoploss_check_windows_result = PositionSimulator._form_stoploss_check_windows(
            pos, klines_data
        )
        if stoploss_check_windows_result is not None:
            stoploss_check_windows, stoplosses_to_check = stoploss_check_windows_result

            # 5. Process (trailing?) stoplosses and finalize the position
            PositionSimulator._process_stoplosses(
                pos,
                klines_data,
                stoploss_check_windows,
                stoplosses_to_check,
            )

    @staticmethod
    def _get_window_slices(
        pos: Position, klines_data: KLinesData
    ) -> tuple[NDArray, NDArray, int]:
        """
        Extracts the relevant price slices based on block indices. Returns two arrays, for finding the
        entry (start time of the block to the end time), and an int, representing the start index of the block by which we
        offset all indices found.
        """
        index_offset = pos.base_block.start_index + 1
        end_index = pos.base_block.end_index + 1 if pos.base_block.end_index else None

        return (
            klines_data.low[index_offset:end_index],
            klines_data.high[index_offset:end_index],
            index_offset,
        )

    @staticmethod
    def _find_entry(
        pos: Position,
        entry_lows: NDArray,
        entry_highs: NDArray,
        offset: int,
    ) -> int | None:
        """Locates the first candle to hit entry."""
        if pos.type == "long":
            entry_cond = entry_lows <= pos.entry
        else:
            entry_cond = entry_highs >= pos.entry

        entry_hits = where(entry_cond)[0]
        if len(entry_hits) == 0:
            return None

        first_entry = entry_hits[0] + offset

        return first_entry

    @staticmethod
    def _process_targets(
        pos: Position,
        klines_data: KLinesData,
        entry_index: int,
    ):
        """Iterates through targets and manages the moving time window."""
        # Define the pool of price data (Highs for Longs, Lows for Shorts)
        target_search_pool = klines_data.high if pos.type == "long" else klines_data.low

        current_window = target_search_pool[entry_index:]
        current_global_offset = entry_index

        target_hit_indices_list = []
        for target in pos.targets:
            hits = (
                where(current_window >= target)[0]
                if pos.type == "long"
                else where(current_window <= target)[0]
            )

            if len(hits) == 0:
                break

            hit_local_index = hits[0]

            # Logic for same-candle entry/target conflict
            if hit_local_index == 0:
                is_candle_green = PositionSimulator._is_candle_green(
                    klines_data, hit_local_index + entry_index
                )
                if not PositionSimulator._is_change_candle_same_direction(
                    is_candle_green, pos.type, "entry", "target"
                ):
                    if len(hits) > 1:
                        hit_local_index = hits[1]
                    else:
                        break

            pos.highest_target += 1
            target_hit_indices_list.append(hit_local_index + current_global_offset)
            pos.target_times.append(
                klines_data.time[hit_local_index + current_global_offset]
            )

            # Slide window forward: next target must occur at or after this one
            current_window = current_window[hit_local_index:]
            current_global_offset += hit_local_index

        pos.target_indices = array(target_hit_indices_list)

    @staticmethod
    def _is_candle_green(klines_data: KLinesData, index: int) -> bool:
        return klines_data.close[index] > klines_data.open[index]

    @staticmethod
    def _is_change_candle_same_direction(
        is_green: bool,
        position_type: Literal["long", "short"],
        first_event: Literal["entry", "target", "stop"],
        second_event: Literal["entry", "target", "stop"],
    ) -> bool:
        """
        Takes a boolean, is_green, as well as the type of the position (long/short)
        and two events.
        Returns True if the first event should be registered before the second event.
        Returns False if the second event should be registered first.

        Args:
            is_green (bool): Whether the color of the candle is green
            position_type (str): Long/short
            first_event, second_event (str): The first and second event, in order, to
                check the possibility for in the candle
        """
        return (
            change_directions_dict[position_type][second_event]
            - change_directions_dict[position_type][first_event]
            > 0
        ) == is_green

    @staticmethod
    def _form_stoploss_check_windows(
        pos: Position,
        klines_data: KLinesData,
    ) -> tuple[list[tuple[int, int, Literal[0, 1, -1]]], list[float]] | None:
        """
        Returns a list of tuples containing window start and end indexes, and a list of stoplosses to check
        for in each of those windows, condensed into a tuple.

        The window tuple also includes an int as a third element which represents which window type it is.
        0 means its a window between the entry and the first target. 1 means a window between two targets, and
        -1 means a window between the non-final target and the last candle. The window between the entry and the
        last candle of the dataframe is also denoted as -1.
        """
        if pos.entry_index is None:
            return None

        # stoplosses_to_check and stoploss_search_windows are some lists to store the search window indexes for easier and more understandable iteration
        stoplosses_to_check: list[float] = [pos.stoplosses[0]]
        stoploss_search_windows: list[tuple[int, int, Literal[0, 1, -1]]]
        if pos.highest_target > 0:
            stoploss_search_windows = [
                (pos.entry_index, int(pos.target_indices[0] + 1), 0)
            ]

            # Add the search windows between the targets
            idx = 0
            stoploss = pos.stoplosses[0]
            for idx, stoploss in enumerate(pos.stoplosses[1 : pos.highest_target], 1):
                stoploss_search_windows.append(
                    (pos.target_indices[idx - 1], pos.target_indices[idx] + 1, 1)
                )
                stoplosses_to_check.append(stoploss)

            # Add the window between the highest (non-full) target and the rest of the candles
            if pos.highest_target != len(pos.targets):
                stoploss_search_windows.append(
                    (pos.target_indices[idx - 1], klines_data.length, -1)
                )
                stoplosses_to_check.append(stoploss)

        # If the highest target is 0, search from the entry to the end of the klines_df
        else:
            stoploss_search_windows = [(pos.entry_index, klines_data.length, -1)]

        return stoploss_search_windows, stoplosses_to_check

    @staticmethod
    def _process_stoplosses(
        pos: Position,
        klines_data: KLinesData,
        stoploss_check_windows: list[tuple[int, int, Literal[-1, 1, 0]]],
        stoplosses_to_check: list[float],
    ):
        """
        Checks the stoploss windows for the stoploss values and updates the required Position
        instance attributes, including highest target, stop time, target times, etc.
        """
        # We now update the highest target hit considering the stoplosses
        pos.highest_target = 0
        for window, stoploss_value in zip(stoploss_check_windows, stoplosses_to_check):
            window_start, window_end, window_type = window
            if pos.type == "long":
                stop_check = where(
                    klines_data.low[window_start:window_end] <= stoploss_value
                )[0]
            else:
                stop_check = where(
                    klines_data.high[window_start:window_end] >= stoploss_value
                )[0]
            # If a stoploss is found, set the stop index and time, and the exit time and type
            # of the position. Also truncate the extra targets that were not hit.
            if len(stop_check) > 0:
                # Check candle direction for registering stops, if the candle registering the stop is the same
                # as another candle registering a target or entry. This can be either the first candle of the
                # window (which can be an entry or a target) or the last candle (Always a target). The last
                # candle isn't checked when it's the last candle of the dataframe.
                stop_index = stop_check[0] + window_start
                is_candle_green = PositionSimulator._is_candle_green(
                    klines_data, stop_check[0] + window_start
                )

                # Window type 0 is the window between the entry and the first target
                if window_type == 0:
                    # If the first candle (the entry candle) also registers a stoploss
                    if stop_check[0] == 0:
                        is_order_correct = (
                            PositionSimulator._is_change_candle_same_direction(
                                is_candle_green, pos.type, "entry", "stop"
                            )
                        )
                        # If the above variable returns True, that means the color of the candle
                        # indicates that the entry PROBABLY happened before the stop, and the stop
                        # is registered on the first candle. Otherwise, it means the stop happened
                        # before the entry and didn't really register, so we set the next stop candle
                        # found, if any, as the stop index.
                        if not is_order_correct:
                            if len(stop_check) > 1:
                                stop_index = stop_check[1] + window_start
                            else:
                                continue
                    # If the last candle (the first target candle) also registers a stoploss
                    # -1 on the window_end because +1 was added to make the window inclusive.
                    elif stop_check[0] + window_start == window_end - 1:
                        is_order_correct = (
                            PositionSimulator._is_change_candle_same_direction(
                                is_candle_green, pos.type, "target", "stop"
                            )
                        )
                        # If the above boolean is True, that means the candle color indicates that
                        # the target occured before the stop, so we don't register the stoploss and
                        # leave it to the next window to register.
                        if is_order_correct:
                            continue

                # Window type 1 is the windows between the targets.
                elif window_type == 1:
                    # If the first candle (target candle) also registers a stoploss
                    if stop_check[0] == 0:
                        is_order_correct = (
                            PositionSimulator._is_change_candle_same_direction(
                                is_candle_green, pos.type, "target", "stop"
                            )
                        )
                        # If the above boolean is true, that means the stoploss happened
                        # after the target, and we don't need to do anything. Otherwise we
                        # need to look for a second stopping candle to register.
                        if not is_order_correct:
                            if len(stop_check) > 1:
                                stop_index = stop_check[1] + window_start
                            else:
                                continue
                    # If the last candle (target candle) also registers a stoploss
                    if stop_check[0] + window_start == window_end - 1:
                        is_order_correct = (
                            PositionSimulator._is_change_candle_same_direction(
                                is_candle_green, pos.type, "target", "stop"
                            )
                        )
                        # If the above boolean is True, that means the target happened before the
                        # stoploss and should be registered as such, so we continue.
                        if is_order_correct:
                            continue

                if stop_index:
                    pos.stop_index = stop_index
                    pos.stop_time = klines_data.time[pos.stop_index]  # pyright: ignore[reportAttributeAccessIssue]
                    pos.stop_price = stoploss_value
                    pos.exit_time = pos.stop_time
                    pos.exit_type = f"STOPLOSS_{pos.highest_target}"
                    pos.target_indices = pos.target_indices[: pos.highest_target]
                    pos.target_times = pos.target_times[: pos.highest_target]

                break
            # If no stop is found in the current window, that means one more target was safely
            # cleared without a stoploss.
            else:
                pos.highest_target += 1

            # If we have hit as many targets as the position has without hitting any SL, register
            # a FULL_TARGET exit type.
            if pos.highest_target == len(pos.targets):
                pos.exit_time = pos.target_times[-1]
                pos.exit_type = "FULL_TARGET"

                break

    @staticmethod
    def _calculate_financial_outcome(pos: Position):
        """Handles the profit/loss math."""
        if not pos.entered:
            return

        total_cap = config.usdt_per_trade * config.leverage
        qty_per_target = (total_cap / pos.entry) / len(pos.targets)
        stop_price = pos.stop_price if pos.stop_price else pos.stoplosses[0]
        hits = pos.highest_target
        misses = len(pos.targets) - hits

        delta = sum(pos.targets[:hits] * qty_per_target) + (
            misses * qty_per_target * stop_price
        )
        if pos.type == "long":
            pos.net_profit = delta - total_cap
        else:
            pos.net_profit = total_cap - delta

        pos.percent_profit = (
            pos.net_profit / config.usdt_per_trade
        ) * 100
