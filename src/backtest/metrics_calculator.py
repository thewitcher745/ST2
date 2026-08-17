from datetime import datetime
from typing import cast
from pandas import DataFrame, Grouper
import pandas as pd


class MetricsCalculator:
    """
    A generic calculator used to calculate metrics from a pandas dataframe
    of position data.
    """

    def calculate(self, positions_df: DataFrame) -> dict[str, float]:
        if positions_df.empty:
            return {}

        # A dataframe of the positions that were entered and exited
        valid_positions_df = DataFrame(
            positions_df[positions_df.entered & positions_df.exited]
        )

        # Prepare time-indexed dataframe for temporal calculations
        time_indexed_df = self._prepare_time_indexed_df(valid_positions_df)

        # Group by month and year
        monthly_groups = self._group_by_month(time_indexed_df)
        yearly_groups = self._group_by_year(time_indexed_df)

        metrics = {
            "total_position_count": len(valid_positions_df),
            "total_winrate": self._total_winrate(valid_positions_df),
            "total_net_profit": self._total_net_profit(valid_positions_df),
            "average_target_hit": self._average_target_hit(valid_positions_df),
            "average_trades_per_month": self._average_trades_per_month(monthly_groups),
            "average_monthly_profit_overall": self._average_monthly_profit_overall(
                monthly_groups
            ),
            "negative_months": self._count_negative_months(monthly_groups),
            "no_trade_months": self._count_no_trade_months(
                time_indexed_df, monthly_groups
            ),
            "max_consecutive_negative_months": self._max_consecutive_negative_months(
                monthly_groups
            ),
            "average_trade_duration": self._average_trade_duration(valid_positions_df),
        }

        # Add per-month net profit
        metrics.update(self._net_profit_per_month(monthly_groups))

        # Add per-month winrate
        metrics.update(self._winrate_per_month(monthly_groups))

        # Add per-month position count
        metrics.update(self._position_count_per_month(monthly_groups))

        # Add per-month drawdown
        metrics.update(self._drawdown_per_month(monthly_groups))

        # Total and average monthly drawdown are added after the per-month
        # drawdown columns so they appear as a summary following them
        metrics["total_drawdown"] = self._total_drawdown(time_indexed_df)
        metrics["average_monthly_drawdown_overall"] = (
            self._average_monthly_drawdown_overall(monthly_groups)
        )

        # Add per-year metrics
        metrics.update(self._metrics_per_year(yearly_groups, monthly_groups))
        metrics["total_performance"] = self._total_performance(monthly_groups)

        return metrics

    # ==================== Data Preparation ====================

    @staticmethod
    def _prepare_time_indexed_df(positions_df: DataFrame) -> DataFrame:
        """Convert entry_time to datetime and set as index for temporal operations."""
        df = positions_df.copy()
        df["entry_time"] = pd.to_datetime(df["entry_time"])
        df["exit_time"] = pd.to_datetime(df["exit_time"])
        df = df.set_index("entry_time")
        return df.sort_index()

    @staticmethod
    def _group_by_month(time_indexed_df: DataFrame) -> dict[str, DataFrame]:
        """Group positions by month, returning dict with 'YYYY-MM' keys."""
        if len(time_indexed_df) == 0:
            return {}

        grouped = time_indexed_df.groupby(Grouper(freq="ME"))
        result = {}

        for period, group in grouped:
            if len(group) > 0:
                month_key = cast(datetime, period).strftime("%Y-%m")
                result[month_key] = group

        return result

    @staticmethod
    def _group_by_year(time_indexed_df: DataFrame) -> dict[int, DataFrame]:
        """Group positions by year, returning dict with year (int) keys."""
        if len(time_indexed_df) == 0:
            return {}

        grouped = time_indexed_df.groupby(Grouper(freq="YE"))
        result = {}

        for period, group in grouped:
            if len(group) > 0:
                result[cast(datetime, period).year] = group

        return result

    # ==================== Basic Metrics ====================

    @staticmethod
    def _total_winrate(positions_df: DataFrame) -> float:
        if len(positions_df) == 0:
            return 0.0
        n_wins = len(positions_df[positions_df.net_profit > 0])
        return n_wins / len(positions_df) * 100

    @staticmethod
    def _total_net_profit(positions_df: DataFrame) -> float:
        return float(positions_df.net_profit.sum())

    @staticmethod
    def _average_target_hit(positions_df: DataFrame) -> float:
        if len(positions_df) == 0:
            return 0.0
        return float(positions_df.highest_target.mean())

    @staticmethod
    def _total_drawdown(time_indexed_df: DataFrame) -> float:
        """
        Calculate the absolute maximum drawdown across the entire equity curve.
        The equity curve is built from the chronological sum of net profits.
        """
        if time_indexed_df.empty or "net_profit" not in time_indexed_df.columns:
            return 0.0

        # We use the time_indexed_df because it is already sorted by entry_time
        equity_curve = time_indexed_df.net_profit.cumsum()
        return MetricsCalculator._max_drawdown(equity_curve)

    # ==================== Monthly Metrics ====================

    @staticmethod
    def _count_no_trade_months(
        time_indexed_df: DataFrame, monthly_groups: dict[str, DataFrame]
    ) -> int:
        """
        Calculates the number of months within the trading period that had zero trades.
        """
        if time_indexed_df.empty:
            return 0

        # Determine the full range of months from first trade to last trade
        first_date = cast(pd.Timestamp, time_indexed_df.index.min())
        last_date = cast(pd.Timestamp, time_indexed_df.index.max())

        start_date = first_date.replace(day=1)
        end_date = last_date.replace(day=1)

        # Generate the expected list of months
        expected_months = pd.date_range(
            start=start_date, end=end_date, freq="MS"
        ).strftime("%Y-%m")

        active_months = set(monthly_groups.keys())
        no_trade_months = [m for m in expected_months if m not in active_months]

        return len(no_trade_months)

    @staticmethod
    def _count_negative_months(monthly_groups: dict[str, DataFrame]) -> int:
        """Count months where net profit is negative."""
        return sum(1 for df in monthly_groups.values() if df.net_profit.sum() < 0)

    @staticmethod
    def _net_profit_per_month(monthly_groups: dict[str, DataFrame]) -> dict:
        """Return dict of net profit per month, 0 for empty months."""
        result = {}
        for month_key, df in monthly_groups.items():
            profit = df.net_profit.sum() if not df.empty else 0.0
            result[f"net_profit_{month_key}"] = profit
        return result

    @staticmethod
    def _winrate_per_month(monthly_groups: dict[str, DataFrame]) -> dict:
        """Return dict of winrate per month."""
        result = {}
        for month_key, df in monthly_groups.items():
            winrate = MetricsCalculator._total_winrate(df) if not df.empty else 0.0
            result[f"winrate_{month_key}"] = winrate
        return result

    @staticmethod
    def _drawdown_per_month(monthly_groups: dict[str, DataFrame]) -> dict:
        """Return dict of max drawdown per month."""
        result = {}
        for month_key, df in monthly_groups.items():
            drawdown = (
                MetricsCalculator._max_drawdown(df.net_profit.cumsum())
                if not df.empty
                else 0.0
            )
            result[f"drawdown_{month_key}"] = drawdown
        return result

    @staticmethod
    def _position_count_per_month(monthly_groups: dict[str, DataFrame]) -> dict:
        """Return dict of position count per month."""
        result = {}
        for month_key, df in monthly_groups.items():
            result[f"position_count_{month_key}"] = len(df)
        return result

    @staticmethod
    def _average_trades_per_month(monthly_groups: dict[str, DataFrame]) -> float:
        if not monthly_groups:
            return 0.0
        trades_per_month = [len(df) for df in monthly_groups.values()]
        return float(sum(trades_per_month) / len(trades_per_month))

    @staticmethod
    def _average_monthly_profit_overall(monthly_groups: dict[str, DataFrame]) -> float:
        if not monthly_groups:
            return 0.0
        monthly_profits = [df.net_profit.sum() for df in monthly_groups.values()]
        return float(sum(monthly_profits) / len(monthly_profits))

    @staticmethod
    def _average_monthly_drawdown_overall(
        monthly_groups: dict[str, DataFrame],
    ) -> float:
        if not monthly_groups:
            return 0.0
        monthly_drawdowns = [
            MetricsCalculator._max_drawdown(df.net_profit.cumsum())
            for df in monthly_groups.values()
        ]
        return float(sum(monthly_drawdowns) / len(monthly_drawdowns))

    @staticmethod
    def _max_drawdown(series: pd.Series) -> float:
        """Compute maximum peak‑to‑trough decline as percentage of peak value."""
        if series.empty:
            return 0.0
        running_max = series.cummax()
        drawdowns = series - running_max
        return float(drawdowns.min())

    @staticmethod
    def _max_consecutive_negative_months(monthly_groups: dict[str, DataFrame]) -> int:
        """Count maximum consecutive months where profit < 0."""
        months = sorted(monthly_groups.items())
        if not months:
            return 0
        profits = [(key, df.net_profit.sum()) for key, df in months]
        max_streak = streak = 0
        for _, val in profits:
            if val < 0:
                streak += 1
            else:
                max_streak = max(max_streak, streak)
                streak = 0
        return max(max_streak, streak)

    @staticmethod
    def _average_trade_duration(positions_df: DataFrame) -> float:
        """Average duration (in hours) between entry_time and exit_time."""
        if len(positions_df) == 0:
            return 0.0
        entry_times = pd.to_datetime(positions_df.entry_time)
        exit_times = pd.to_datetime(positions_df.exit_time)
        durations = (exit_times - entry_times).dropna()
        avg_duration = durations.mean()
        return (
            avg_duration.total_seconds() / 3600.0 if not pd.isna(avg_duration) else 0.0
        )

    # ==================== Yearly Metrics ====================

    @staticmethod
    def _metrics_per_year(
        yearly_groups: dict[int, DataFrame], monthly_groups: dict[str, DataFrame]
    ) -> dict:
        results = {}
        for year, year_df in yearly_groups.items():
            # Corresponding months for that year
            year_months = {
                m: df for m, df in monthly_groups.items() if m.startswith(str(year))
            }
            if not year_months:
                continue

            monthly_profits = [df.net_profit.sum() for df in year_months.values()]
            positive = sum(1 for p in monthly_profits if p > 0)
            total = len(monthly_profits)
            performance = (positive / total * 100) if total else 0

            results.update(
                {
                    f"total_profit_{year}": year_df.net_profit.sum(),
                    f"performance_{year}": performance,
                    f"average_monthly_profit_{year}": sum(monthly_profits) / total
                    if total
                    else 0.0,
                    f"average_monthly_drawdown_{year}": sum(
                        MetricsCalculator._max_drawdown(df.net_profit.cumsum())
                        for df in year_months.values()
                    )
                    / total
                    if total
                    else 0.0,
                }
            )

        return results

    # ==================== Overall Performance ====================

    @staticmethod
    def _total_performance(monthly_groups: dict[str, DataFrame]) -> float:
        """
        Calculate overall performance: percentage of profitable months across entire period.
        """
        if not monthly_groups:
            return 0.0
        monthly_profits = [df.net_profit.sum() for df in monthly_groups.values()]
        positive_months = sum(1 for p in monthly_profits if p > 0)
        return (
            (positive_months / len(monthly_profits) * 100) if monthly_profits else 0.0
        )
