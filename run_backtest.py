from datetime import datetime
import logging
from pathlib import Path

from src.backtest.results_aggregator import ResultsAggregator
from src.backtest.config_generator import ConfigurationGenerator
from src.config import Config
from src.backtest.backtest_executor import BacktestExecutor
from src.backtest.visualization import VisualizationEngine
from src.backtest.metrics_calculator import MetricsCalculator

config = Config()
logger = logging.getLogger("[BacktestMain]")
BACKTEST_START_DATE = "20260101"
BACKTEST_END_DATE = "20260801"


def get_backtest_output_filepath() -> str:
    output_dir = config.backtest_output_dir or "outputs"
    output_path = Path(output_dir)

    if not output_path.is_absolute() and output_path.parent == Path("."):
        output_path = Path("outputs") / output_path

    return str(output_path / "cases.csv")


def format_duration(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


params_range_dict = {
    # "lag": [6, 7, 8, 9, 10, 11, 12],
    "target_setup_function": [
        "small_blocks_refined_t1_only",
        "default_t1_only",
        # "small_blocks_refined_t1_t2_only",
        # "default_t1_t2_only",
        # "small_blocks_refined_t1_t2_t3_only",
        # "default_t1_t2_t3_only",
    ],
    "stoploss_setup_function": [
        "default",
        "small_blocks_refined_no_trailing",
        # "small_blocks_refined_trailing_breakeven_t1",
        # "trailing_breakeven_t1",
        # "small_blocks_refined_trailing_breakeven_t2",
        # "trailing_breakeven_t2",
    ],
    "block_types": ["OB", "BB", "MB", "OB/BB", "OB/MB", "MB/BB", "OB/MB/BB"],
    "timeframe": ["4h"],
    "target_coeff": [
        0.5,
        0.6,
        0.75,
        1.0,
        1.1,
        1.2,
        1.3,
        1.4,
        1.5,
        1.6,
        1.75,
        2,
        2.25,
        2.5,
        2.75,
        3,
    ],
    "stoploss_coeff": [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.75, 2, 2.25, 2.5, 2.75, 3],
    "max_bounces": [1, 2, 3],
}
results_aggregator = ResultsAggregator(
    get_backtest_output_filepath(), params_range_dict
)
results_aggregator_long = ResultsAggregator(
    "cases_long.csv",
    params_range_dict,
    output_dir=results_aggregator.output_dir,
)
results_aggregator_short = ResultsAggregator(
    "cases_short.csv",
    params_range_dict,
    output_dir=results_aggregator.output_dir,
)
metrics_calculator = MetricsCalculator()

logger.info("New backtest initiation")
config_gen = ConfigurationGenerator(params_range_dict)

total_cases_count = config_gen.count
logger.info(f"{total_cases_count} cases to run.")

current_count = 1
backtest_started_at = datetime.now()

symbols = ["BTCUSDT"]

print("Getting data and running backtests for ", symbols)
results_aggregator.save_config_json(
    symbols,
    extra_config={
        "backtest_start_date": BACKTEST_START_DATE,
        "backtest_end_date": BACKTEST_END_DATE,
    },
)

for run_id, config_combo_dict in config_gen:
    if current_count % 10 == 0:
        logger.info(f"Running case {current_count}/{total_cases_count}")

    if current_count % 100 == 0:
        now = datetime.now()
        elapsed_seconds = (now - backtest_started_at).total_seconds()
        completed_cases = current_count - 1
        average_case_duration = (
            elapsed_seconds / completed_cases if completed_cases else 0
        )
        remaining_cases = total_cases_count - completed_cases
        eta_seconds = average_case_duration * remaining_cases
        estimated_completion = datetime.fromtimestamp(now.timestamp() + eta_seconds)
        logger.info(
            "ETA after %s/%s cases: remaining=%s, estimated_completion=%s",
            completed_cases,
            total_cases_count,
            format_duration(eta_seconds),
            estimated_completion.strftime("%Y-%m-%d %H:%M:%S"),
        )

    config_gen.override_config_with_combo(config_combo_dict)
    bt_exec = BacktestExecutor()

    start_time = datetime.strptime(BACKTEST_START_DATE, "%Y%m%d")
    end_time = datetime.strptime(BACKTEST_END_DATE, "%Y%m%d")

    positions_df = bt_exec.execute(symbols, start_time, end_time)
    # positions_df[positions_df.exited].to_csv("backtest_positions.csv")

    metrics_dict = metrics_calculator.calculate(positions_df=positions_df)
    long_metrics_dict = metrics_calculator.calculate(
        positions_df=positions_df[positions_df.type == "long"]
    )
    short_metrics_dict = metrics_calculator.calculate(
        positions_df=positions_df[positions_df.type == "short"]
    )

    results_aggregator.append_result(run_id, config_combo_dict, metrics_dict)
    results_aggregator_long.append_result(run_id, config_combo_dict, long_metrics_dict)
    results_aggregator_short.append_result(
        run_id, config_combo_dict, short_metrics_dict
    )

    current_count += 1

results_aggregator.to_csv(
    symbols,
    extra_config={
        "backtest_start_date": BACKTEST_START_DATE,
        "backtest_end_date": BACKTEST_END_DATE,
    },
)
results_aggregator_long.save_excel_only("cases_long.xlsx")
results_aggregator_short.save_excel_only("cases_short.xlsx")

engine = VisualizationEngine(results_aggregator)
engine.generate_all_visualizations(save_pdf=True, save_individual=True)
