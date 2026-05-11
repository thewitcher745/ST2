from datetime import datetime
import logging

from src.backtest.results_aggregator import ResultsAggregator
from src.backtest.config_generator import ConfigurationGenerator
from src.config import Config
from src.backtest.backtest_executor import BacktestExecutor
from src.backtest.visualization import VisualizationEngine
from src.backtest.metrics_calculator import MetricsCalculator

config = Config()
logger = logging.getLogger("[BacktestMain]")

params_range_dict = {
    # "lag": [6, 7, 8, 9, 10, 11, 12],
    "target_setup_function": ["small_blocks_refined", "default"],
    "stoploss_setup_function": [
        "small_blocks_refined_no_trailing",
        "small_blocks_refined_trailing_breakeven_t1",
        "trailing_breakeven_t1",
        "default",
    ],
    "block_types": ["OB", "BB", "MB", "OB/BB", "OB/MB", "MB/BB", "OB/MB/BB"],
    "timeframe": ["5m", "15m", "30m", "1h", "4h"],
    "target_coeff": [0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.3, 1.4, 1.5],
    "stoploss_coeff": [0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.3, 1.4, 1.5],
    "max_bounces": [1, 2, 3],
}
results_aggregator = ResultsAggregator("outputs/cases.csv", params_range_dict)

logger.info("New backtest initiation")
config_gen = ConfigurationGenerator(params_range_dict)

total_cases_count = config_gen.count
logger.info(f"{total_cases_count} cases to run.")

current_count = 1

for run_id, config_combo_dict in config_gen:
    if current_count % 10 == 0:
        logger.info(f"Running case {current_count}/{total_cases_count}")

    config_gen.override_config_with_combo(config_combo_dict)
    bt_exec = BacktestExecutor()
    symbols = ["XAUUSDT"]
    start_time = datetime(year=2025, month=5, day=1)
    end_time = datetime(year=2026, month=5, day=1)

    positions_df = bt_exec.execute(symbols, start_time, end_time)
    positions_df[positions_df.entered & positions_df.exited].to_csv(
        "backtest_main_positions.csv"
    )

    metrics_dict = MetricsCalculator().calculate(positions_df=positions_df)

    results_aggregator.append_result(run_id, config_combo_dict, metrics_dict)

    current_count += 1

results_aggregator.to_csv()

engine = VisualizationEngine(results_aggregator)
engine.generate_all_visualizations(save_pdf=True, save_individual=True)
