from pandas import DataFrame
from pathlib import Path
from datetime import datetime
import json

from src.config import Config


class ResultsAggregator:
    """Class uses to combine config combo data and metrics data for that combo."""

    def __init__(self, output_filepath: str, params_range_dict: dict):
        """
        Args:
            output_filepath: Base path for output (will be placed in timestamped folder)
            params_range_dict: The parameter ranges being tested
        """
        self.output_filepath = output_filepath

        self.rows: list[dict] = []
        self.params_range_dict = params_range_dict
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = Path(output_filepath).parent / self.timestamp
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def append_result(self, run_id: str, combo_dict: dict, metrics_dict: dict):
        """Adds a row to the list of rows."""
        self.rows.append({"run_id": run_id, **combo_dict, **metrics_dict})

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

    def _save_config_json(self):
        """Save full config with constants and ranges to JSON."""
        config = Config()
        full_config = {}

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

    def to_csv(self):
        """
        Creates a pandas dataframe with the rows and saves to timestamped folder.
        Also saves the config JSON.
        """
        self.calculate_scores()

        # Save CSV
        csv_path = self.output_dir / Path(self.output_filepath).name
        DataFrame(self.rows).to_csv(csv_path, index=False)

        # Save config JSON
        self._save_config_json()

        print(f"Results saved to: {self.output_dir}")
