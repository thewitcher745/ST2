# Backtesting and results

[Project README](../README.md) · [Documentation index](README.md) · [Positions](positions.md) · [Configuration](configuration.md)

[run_backtest.py](../run_backtest.py) runs a Cartesian product of strategy parameters over historical Binance Futures candles. It calculates combined, long-only, and short-only metrics for each case, then exports spreadsheets and analysis figures.

## Configure an experiment

Edit these variables in the runner:

| Variable | Purpose |
| --- | --- |
| `BACKTEST_START_DATE` | Start date in `YYYYMMDD` format. |
| `BACKTEST_END_DATE` | End date in `YYYYMMDD` format. |
| `symbols` | Explicit list of Binance Futures symbols. This is independent of `-s`. |
| `params_range_dict` | Configuration keys mapped to lists of values to sweep. |

The current script uses January 1, 2026 through October 1, 2026, `XAUUSDT`, and a 9,464-case grid. A small first experiment could replace the grid with:

```python
params_range_dict = {
    "structure_engine": ["pine_replay"],
    "timeframe": ["1h"],
    "block_types": ["OB", "OB/BB"],
    "target_setup_function": ["default_t1_only"],
    "stoploss_setup_function": ["default"],
    "target_coeff": [1.0, 1.5],
    "stoploss_coeff": [1.0],
    "max_bounces": [1],
}
```

That grid contains four combinations. Parameters absent from the grid retain their loaded configuration values. The generator checks that keys exist in the schema, but assigns values directly without typecasting or validating combinations, so use properly typed Python values.

```bash
python run_backtest.py --backtest_output_dir first_run
```

No Telegram messages are sent by this entry point. There are no CLI start/end date or sweep-range options; edit the script. The runner executes at module level, so importing `run_backtest` also launches its experiment. Import the classes under `src/backtest/` when writing a separate analysis script.

## Execution flow

1. [ConfigurationGenerator](../src/backtest/config_generator.py) enumerates the product of the parameter lists and creates a 12-character MD5-based case ID from each combination dictionary.
2. The combination overrides the shared `Config` singleton. A new [BacktestExecutor](../src/backtest/backtest_executor.py) is constructed.
3. For each symbol, the executor loads candles, calculates structure and block lifetimes, then simulates positions from all accepted blocks.
4. [MetricsCalculator](../src/backtest/metrics_calculator.py) calculates metrics for all positions and separately for long and short positions.
5. Aggregators retain rows in memory. After the sweep, the runner writes tables, computes scores, and generates report plots.

The runner logs progress every ten cases and estimates completion time every hundred cases. Results are not checkpointed per case; `config.json` is written at the beginning and again at export, while the result tables are written after all cases finish.

For `pine_replay`, the detector reads the current `lag` and `fib_factor` each calculation. In the bulk pipeline, the default arguments of `Zigzag()` and `MSBIdentifier()` capture those values at module import. Sweeping these two keys alone therefore does not reliably change the bulk instances' parameters in the current executor; pass explicit constructor values when extending that workflow.

## Historical data and cache

[LocalDataProvider](../src/data_provider/historical/local_data.py) stores Feather files under `data/klines/<run_id>/`. Each filename includes the symbol, timeframe, start time, and end time. Matching requests reuse the file, so cases with the same data request avoid repeated downloads.

On a cache miss, [BinanceDataProvider](../src/data_provider/historical/binance_cache.py) requests Futures klines with public credentials by default. It returns `time`, `open`, `high`, `low`, and `close`; prices become floats and timestamps become timezone-naive UTC. The last response row is dropped by `get_klines()`, including for a fixed historical date request.

`startup_n_days` does not add a warmup before `BACKTEST_START_DATE`; the requested range is the detector's whole input. If you need earlier structure history, account for that in your experiment and analysis. A cached file is reused as-is and is not automatically refreshed. The forward runner's `--clear_klines` cleanup is not called by `run_backtest.py`.

## Output paths and files

Each experiment creates a timestamped directory with the format `YYYYMMDD_HHMMSS`.

| Argument | Resulting base directory |
| --- | --- |
| Omitted | `outputs/` |
| `--backtest_output_dir first_run` | `outputs/first_run/` |
| `--backtest_output_dir experiments/gold` | `experiments/gold/` |
| An absolute directory | That directory |

All three result aggregators share the same experiment directory:

```text
outputs/first_run/<timestamp>/
  config.json
  cases.csv
  cases.xlsx
  cases_long.xlsx
  cases_short.xlsx
  filtered_results.xlsx          # Only when at least one case passes
  backtest_analysis_report.pdf
  01_multi_objective_correlations.png
  02_parameter_impact_comparison.png
  03_pareto_front.png
  04_parameter_sensitivity.png
  05_top_configurations.png
```

`cases.csv` and `cases.xlsx` contain one row per combined case: case ID in `run_id`, swept parameters, metrics, and score. Long and short results are exported as Excel files only. The current runner does not export individual position histories; it has a commented position-CSV line that can be enabled for a focused run.

`config.json` contains symbols, sweep lists, fixed settings, and the backtest dates. The exporter includes all public loaded configuration attributes, including Telegram credentials when present. Redact those fields before sharing the folder.

`filtered_results.xlsx` includes cases meeting **all** of these conditions: positive total profit, win rate at least 30%, at most one consecutive negative active month, and at most two negative months. It separates sheets by timeframe when that column is present. These are export filters, not strategy execution rules.

## Metric definitions

Metrics include only positions with both `entered=True` and `exited=True`. Open and never-entered positions are excluded. Trades are sorted and grouped by **entry time**, including when their exit falls in a later month or year.

| Metric | Definition |
| --- | --- |
| `total_position_count` | Number of entered and exited positions. |
| `total_winrate` | Percentage of closed positions with `net_profit > 0`; zero-profit trades are not wins. |
| `total_net_profit` | Sum of closed positions' USDT profit. |
| `average_target_hit` | Mean `highest_target` across closed positions. |
| `average_trade_duration` | Mean time from entry to exit, in hours. |
| `average_trades_per_month` | Mean closed-trade count over months represented by at least one closed trade. |
| `average_monthly_profit_overall` | Mean profit over those active months. |
| `negative_months` | Number of active months with profit strictly below zero. |
| `no_trade_months` | Missing months between the first and last closed trade's entry month. Does not include empty months outside those bounds. |
| `max_consecutive_negative_months` | Longest negative streak in the sorted active-month groups. Empty calendar months are omitted rather than breaking the streak. |
| `total_performance` | Percentage of active months with profit strictly above zero. |

Each active month also produces `net_profit_YYYY-MM`, `winrate_YYYY-MM`, `position_count_YYYY-MM`, and `drawdown_YYYY-MM`. Yearly columns include `total_profit_YYYY`, `performance_YYYY`, `average_monthly_profit_YYYY`, and `average_monthly_drawdown_YYYY`.

### Drawdown

The actual calculation is:

```text
equity = cumulative sum of net_profit, sorted by entry_time
drawdown = min(equity - equity.cummax())
```

Drawdown values are **non-positive USDT amounts**, despite a percentage description in the helper's docstring. `total_drawdown` applies this to all closed trades; monthly drawdowns restart the cumulative sum inside each active month. `average_monthly_drawdown_overall` averages those monthly values.

The series is not seeded with zero or an account balance. Consequently, an initial loss is not measured as a decline from an initial zero point. This metric also attributes the entire eventual P&L to entry order, rather than maintaining an exit-time account equity curve.

## Scores and report plots

[ResultsAggregator](../src/backtest/results_aggregator.py) normalizes each score metric within that aggregator's cases:

```text
normalized = (value - minimum) / (maximum - minimum)
```

If all values are equal, the normalized contribution is `0.5`. Lower-is-better metrics are inverted with `1 - normalized`.

| Metric | Weight | Preferred direction |
| --- | --- | --- |
| `total_winrate` | 1.0 | Higher |
| `total_performance` | 1.5 | Higher |
| `total_net_profit` | 2.0 | Higher |
| `average_target_hit` | 1.0 | Higher |
| `average_monthly_drawdown_overall` | 1.5 | Higher, meaning closer to zero |
| `max_consecutive_negative_months` | 1.0 | Lower |
| `no_trade_months` | 1.0 | Lower |

The score is the weighted sum, with maximum 9 when all metrics are available. It is a relative ranking within an experiment. Long, short, and combined aggregators normalize independently, so their scores are not on a shared absolute scale.

The report contains correlations, parameter impact, a multi-objective trade-off scatter plot, sensitivity plots, and top-configuration tables. Categorical parameter values are encoded as integer codes for correlation; interpret those correlations with that arbitrary ordering in mind. The figure called “Pareto Front” plots the case results; it does not filter them to a mathematically computed nondominated frontier. See [charts](charts.md).

## Simulation assumptions and implementation limits

The simulation uses the strategy timeframe's OHLC candles, with candle-color heuristics for some same-candle event conflicts. It assumes fills at planned levels and models no commissions, funding, slippage, liquidation, portfolio margin, compounding, or limit-order queue. A hit is a simulated event, not an exchange fill.

Positions from different blocks and bounces can overlap. Bounces can begin searching at the threshold-target candle before the preceding attempt has exited. An entered position's targets and stops can outlive its block. Unclosed positions have no mark-to-market contribution. Weighted target exits change the P&L, but their allocation is not sent to Telegram.

The simulator is a collection of separate target and stop searches rather than a full chronological tick replay. In particular, the tail stop window after a non-final target currently starts at `target_indices[idx - 1]`; after only T1 this can select the last precomputed target index. Some same-candle `continue` branches also affect target accounting. Inspect individual position events for strategies sensitive to these boundaries rather than assuming exact intrabar sequencing.

Fetching or calculation errors are logged per symbol and that symbol is skipped. If every symbol fails or no positions exist, the runner can reach its long/short slicing or filtered-export code without required columns and raise an error. Start with a small successful experiment and inspect the backtest log when reports are empty.

`--shutdown` invokes host shutdown only after all exports and visualizations finish successfully. Omit it during interactive work. Continue with [forward testing](forward-testing.md) to understand how live behavior differs.
