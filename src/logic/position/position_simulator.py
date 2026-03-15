from numpy import where, ndarray
from .position import Position
from ...data_provider import KLinesData
from ...config import Config

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
        entry_lows, entry_highs, stop_lows, stop_highs, index_offset = (
            PositionSimulator._get_window_slices(pos, klines_data)
        )

        # 2. Find Entry and Stoploss indices
        entry_index, stop_index = PositionSimulator._find_primary_events(
            pos, entry_lows, entry_highs, stop_lows, stop_highs, index_offset
        )

        if entry_index is None:
            return

        pos.status = "ENTERED"
        pos.entry_time = klines_data.time[entry_index]

        if stop_index:
            pos.stop_time = klines_data.time[stop_index]

        # 3. Process Targets
        PositionSimulator._process_targets(
            pos, klines_data, entry_index, stop_index, index_offset
        )

        # 4. Finalize Status
        PositionSimulator._finalize_status(pos)

    @staticmethod
    def _get_window_slices(
        pos: Position, klines_data: KLinesData
    ) -> tuple[ndarray, ndarray, int]:
        """
        Extracts the relevant price slices based on block indices. Returns four arrays, two for finding the
        entry (start time of the block to the end time), two for finding the stoploss (start time of the block
        to the end of the klines dataframe) and an int, representing the start index of the block by which we
        offset all indices found.
        """
        index_offset = pos.base_block.start_index + 1
        end_index = pos.base_block.end_index + 1 if pos.base_block.end_index else None

        return (
            klines_data.low[index_offset:end_index],
            klines_data.high[index_offset:end_index],
            klines_data.low[index_offset:],
            klines_data.high[index_offset:],
            index_offset,
        )

    @staticmethod
    def _find_primary_events(
        pos: Position,
        entry_lows: ndarray,
        entry_highs: ndarray,
        stop_lows: ndarray,
        stop_highs: ndarray,
        offset: int,
    ) -> tuple[int | None, int | None]:
        """Locates the first candle to hit entry and stoploss."""
        if pos.type == "long":
            entry_cond = entry_lows <= pos.entry
            stop_cond = stop_lows <= pos.stoploss
        else:
            entry_cond = entry_highs >= pos.entry
            stop_cond = stop_highs >= pos.stoploss

        entry_hits = where(entry_cond)[0]
        if len(entry_hits) == 0:
            return None, None

        first_entry = entry_hits[0] + offset

        stop_hits = where(stop_cond)[0]
        first_stop = (stop_hits[0] + offset) if len(stop_hits) > 0 else None

        return first_entry, first_stop

    @staticmethod
    def _process_targets(
        pos: Position,
        klines: KLinesData,
        entry_index: int,
        stop_index: int | None,
        offset: int,
    ):
        """Iterates through targets and manages the moving time window."""
        # Define the pool of price data (Highs for Longs, Lows for Shorts)
        extrema_pool = klines.high if pos.type == "long" else klines.low

        # Define the search window between entry and stop
        search_end = stop_index if stop_index else len(extrema_pool)
        current_window = extrema_pool[entry_index:search_end]
        current_global_offset = entry_index

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
                if not PositionSimulator._is_valid_same_candle_hit(
                    pos, klines, current_global_offset
                ):
                    if len(hits) > 1:
                        hit_local_index = hits[1]
                    else:
                        break

            pos.highest_target += 1
            pos.target_times.append(
                klines.time[hit_local_index + current_global_offset]
            )

            # Slide window forward: next target must occur at or after this one
            current_window = current_window[hit_local_index:]
            current_global_offset += hit_local_index

    @staticmethod
    def _is_valid_same_candle_hit(
        pos: Position, klines: KLinesData, index: int
    ) -> bool:
        """Determines if a target hit on the entry candle is valid based on candle color."""
        is_green = klines.close[index] > klines.open[index]
        if pos.type == "long":
            return is_green  # Assume entry before target in green candles
        return not is_green  # Assume entry before target in red candles

    @staticmethod
    def _finalize_status(pos: Position):
        """Sets the final status string based on simulation results."""
        if pos.highest_target > 0:
            pos.status = f"TARGET_{pos.highest_target}"
            if pos.highest_target == len(pos.targets):
                pos.full_target = True
                pos.stop_time = None
        elif pos.status == "ENTERED":
            pos.status = "STOPLOSS"

    @staticmethod
    def _calculate_financial_outcome(pos: Position):
        """Handles the profit/loss math."""
        if pos.status == "NOT_ENTERED":
            return

        total_cap = float(config.usdt_per_trade) * float(config.leverage)
        qty_per_target = (total_cap / pos.entry) / len(pos.targets)

        hits = pos.highest_target
        misses = len(pos.targets) - hits

        delta = sum(pos.targets[:hits] * qty_per_target) + (
            misses * qty_per_target * pos.stoploss
        )
        if pos.type == "long":
            pos.net_profit = delta - total_cap
        else:
            pos.net_profit = total_cap - delta

        pos.percent_profit = (pos.net_profit / float(config.usdt_per_trade)) * 100
