from typing import cast
from pandas import DataFrame
from pathlib import Path
from datetime import datetime
import pandas as pd
import json
import logging

from src.config import Config

logger = logging.getLogger("[BacktestResultsAggregator]")


class ResultsAggregator:
    """Class uses to combine config combo data and metrics data for that combo."""

    def __init__(
        self,
        output_filepath: str,
        params_range_dict: dict,
        output_dir: Path | None = None,
    ):
        """
        Args:
            output_filepath: Base path for output (will be placed in timestamped folder)
            params_range_dict: The parameter ranges being tested
            output_dir: Optional explicit output directory to use instead of
                generating a new timestamped folder.
        """
        self.output_filepath = output_filepath

        self.rows: list[dict] = []
        self.params_range_dict = params_range_dict
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = (
            Path(output_dir)
            if output_dir is not None
            else Path(output_filepath).parent / self.timestamp
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def append_result(self, run_id: str, combo_dict: dict, metrics_dict: dict):
        """Adds a row to the list of rows."""
        self.rows.append({"run_id": run_id, **combo_dict, **metrics_dict})

    def to_dataframe(self) -> DataFrame:
        self.calculate_scores()
        return self._reorder_columns(DataFrame(self.rows))

    def _reorder_columns(self, df: DataFrame) -> DataFrame:
        if df.empty:
            return df

        config_cols = ["run_id"] + list(self.params_range_dict.keys())

        summary_metric_cols = [
            "total_position_count",
            "total_winrate",
            "total_net_profit",
            "average_target_hit",
            "average_trades_per_month",
            "average_monthly_profit_overall",
            "no_trade_months",
            "negative_months",
            "max_consecutive_negative_months",
            "average_trade_duration",
            "total_drawdown",
            "average_monthly_drawdown_overall",
            "total_profit_2026",
            "performance_2026",
            "average_monthly_profit_2026",
            "average_monthly_drawdown_2026",
            "total_performance",
            "score",
        ]

        monthly_prefix_order = [
            "net_profit_",
            "winrate_",
            "position_count_",
            "drawdown_",
        ]

        present_config_cols = [col for col in config_cols if col in df.columns]
        present_summary_metric_cols = [
            col for col in summary_metric_cols if col in df.columns
        ]

        ordered_monthly_cols: list[str] = []
        for prefix in monthly_prefix_order:
            ordered_monthly_cols.extend(
                sorted(
                    [
                        col
                        for col in df.columns
                        if col.startswith(prefix) and col not in ordered_monthly_cols
                    ]
                )
            )

        ordered_cols = (
            present_config_cols + present_summary_metric_cols + ordered_monthly_cols
        )
        ordered_cols.extend(
            [col for col in df.columns if col not in ordered_cols]
        )

        return df[ordered_cols]

    def calculate_scores(self):
        """
        Calculate normalized scores after all results are collected.
        Normalizes each metric to [0, 1] and combines with weights.
        """
        if not self.rows:
            return

        df = DataFrame(self.rows)

        # Define metrics and their weights (metric_name: (weight, is_negative))
        # is_negative=True means lower is better (inverted during scoring)
        metrics_config = {
            "total_winrate": (1.0, False),
            "total_performance": (1.5, False),
            "total_net_profit": (2.0, False),
            "average_target_hit": (1.0, False),
            "average_monthly_drawdown_overall": (
                1.5,
                False,
            ),  # Drawdowns are negative so higher is better
            "max_consecutive_negative_months": (1.0, True),
            "no_trade_months": (1.0, True),
        }

        score = 0
        for metric, (weight, is_negative) in metrics_config.items():
            if metric not in df.columns:
                continue

            col = df[metric]
            # Handle edge case where all values are the same
            if col.max() == col.min():
                normalized = 0.5
            else:
                normalized = (col - col.min()) / (col.max() - col.min())

            if is_negative:
                normalized = 1 - normalized

            score += weight * normalized

        df["score"] = score
        self.rows = df.to_dict("records")

    def save_config_json(self, symbols: list[str]):
        """
        Save full config with constants and ranges to JSON.

        Args:
            List of symbols to write to the config file.
        """
        config = Config()
        full_config = {"symbols": symbols}

        # Add all config attributes
        for attr in dir(config):
            if attr.startswith("_") or callable(getattr(config, attr)):
                continue

            value = getattr(config, attr)
            # If this param is in the range dict, show as list, otherwise as constant
            if attr in self.params_range_dict:
                full_config[attr] = self.params_range_dict[attr]
            else:
                full_config[attr] = value

        config_path = self.output_dir / "config.json"
        with open(config_path, "w") as f:
            json.dump(full_config, f, indent=2, default=str)

    def to_csv(self, symbols: list[str]):
        """
        Creates a pandas dataframe with the rows and saves to timestamped folder.
        Also saves the config JSON and Excel files.

        Args:
            symbols: List of symbols to write to the config.json
        """
        df = self.to_dataframe()

        # Save CSV
        csv_path = self.output_dir / Path(self.output_filepath).name
        df.to_csv(csv_path, index=False)

        # Save full Excel
        excel_path = (
            self.output_dir / Path(self.output_filepath).with_suffix(".xlsx").name
        )
        self._save_full_excel(df, excel_path)

        # Save filtered Excel
        self._save_filtered_excel(df)

        # Save config JSON
        self.save_config_json(symbols)

        logger.info(f"Results saved to: {self.output_dir}")

    def save_excel_only(self, output_filename: str):
        df = self.to_dataframe()
        excel_path = self.output_dir / output_filename
        self._save_full_excel(df, excel_path)
        logger.info(f"Excel results saved to: {excel_path}")

    def _save_full_excel(self, df: DataFrame, excel_path: Path):
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            if "case_name" in df.columns:
                for case_name in df["case_name"].dropna().unique():
                    case_df = df[df["case_name"] == case_name]
                    sheet_name = str(case_name)[:31]
                    case_df.to_excel(writer, sheet_name=sheet_name, index=False)
            else:
                df.to_excel(writer, sheet_name="All", index=False)

    def _save_filtered_excel(self, df: DataFrame):
        """
        Save filtered Excel with:
        - Filter: total_net_profit > 0
        - Filter: total_winrate >= 30
        - Filter: max_consecutive_negative_months <= 1
        - Filter: negative_months <= 2
        - Separate sheets per timeframe
        - Reordered columns: config params, key metrics, then rest
        """
        # Filter rows
        filtered_df = df[
            (df["total_net_profit"] > 0)
            & (df["total_winrate"] >= 30)
            & (df["max_consecutive_negative_months"] <= 1)
            & (df["negative_months"] <= 2)
        ].copy()

        if filtered_df.empty:
            logger.info("No rows passed the filter criteria")
            return

        filtered_df = self._reorder_columns(filtered_df)

        filtered_df = cast(DataFrame, filtered_df)

        # Save to Excel with sheets per timeframe
        excel_filtered_path = self.output_dir / "filtered_results.xlsx"

        with pd.ExcelWriter(excel_filtered_path, engine="openpyxl") as writer:
            if "timeframe" in filtered_df.columns:
                for tf in filtered_df["timeframe"].unique():
                    tf_df = filtered_df[filtered_df["timeframe"] == tf]
                    tf_df.to_excel(writer, sheet_name=str(tf), index=False)
            else:
                filtered_df.to_excel(writer, sheet_name="All", index=False)

        logger.info(f"Filtered results saved to: {excel_filtered_path}")
