# Charts and visualization

[Project README](../README.md) · [Documentation index](README.md) · [Forward testing](forward-testing.md) · [Backtesting](backtesting.md)

ST2 has three visualization paths: a live desktop viewer, programmatically generated Plotly HTML charts, and static analysis figures exported after a backtest sweep.

## Live desktop viewer

Install the extra desktop dependencies, then launch the viewer from the repository root:

```bash
python -m pip install PyQt6 pyqtgraph
python chart.py
```

Start a normal or dry forward test first so `data/chart/` exists and contains a run directory. The viewer is a separate process: it reads snapshots and does not connect to Binance or recalculate the strategy itself.

Select **Run ID**, then **Symbol**. The viewer reads `data/chart/<run_id>/<SYMBOL>.pack` every two seconds. The forward test writes these files at intervals controlled by `calc_interval`, so polling can be faster than new data arrives. The `chart_data_write_interval` setting is currently unused.

The chart displays:

- Candles and the detected zigzag.
- Bullish blocks in green and bearish blocks in red.
- Candle count, block count, latest close, latest candle time, and snapshot update time.
- A crosshair with candle index, timestamp, and OHLC values.
- Clickable blocks showing ID, type, direction, high/low, and start/end times. Clicking toggles highlighting, including the extension toward the base candle.

The default view follows the most recent 80 candles. Manually panning or zooming pauses automatic zoom for 60 seconds. Selecting a symbol reapplies automatic zoom when permitted by that timeout. Run-directory choices are populated when the window starts; restart the viewer if you create a new run afterward.

Snapshots contain candles, accepted blocks, and zigzag points, rather than a full position-event history or a Telegram delivery log. Normal forward startup clears the selected run's previous snapshots.

## Interactive HTML charts

[ChartManager](../src/visualization/chart.py) builds Plotly charts with candles, labeled pivots, MSBs, blocks, and simulated position paths. This is a programmatic API; `chart.py` launches the desktop viewer instead.

For example, save this as a local script in the repository root and run it in the configured environment:

```python
from datetime import datetime

import pandas as pd

from src.config import Config
from src.data_provider import KLinesData, LocalDataProvider
from src.logic import BlockManager, MSBIdentifier, PositionManager, Zigzag
from src.visualization import ChartManager

config = Config()
symbol = "BTCUSDT"
df = LocalDataProvider().get_klines(
    symbol,
    config.timeframe,
    datetime(2026, 1, 1),
    datetime(2026, 2, 1),
)
data = KLinesData(df)
blocks = BlockManager()
zigzag_df, msbs_df = blocks.calculate_structure(data, Zigzag(), MSBIdentifier())
positions = PositionManager()
positions.simulate_and_generate_positions(blocks.all_blocks_aslist, data)

chart = ChartManager(title=f"{symbol} structure", output_file="chart.html")
chart.add_candlesticks(df)
chart.add_zigzag(zigzag_df)
chart.add_msb(msbs_df, zigzag_df)
chart.add_blocks(
    pd.DataFrame([block.to_dict() for block in blocks.all_blocks_aslist]),
    last_time=df.time.iloc[-1],
    draw_base_candle_extension=True,
)
chart.add_positions(positions.to_dataframe())
chart.save(auto_open=False)
```

This example fetches or reuses historical data, then saves `chart.html`. Open that file in a browser. `chart.show()` is also available to display the figure through Plotly's renderer. Importing `src.visualization` currently imports the desktop viewer too, so its PyQt6 and pyqtgraph dependencies must be installed even for this HTML example.

Saved HTML includes a **Zoom to candle time or block ID** field. Enter a timestamp such as `2026-01-15 12:00:00` or a block ID such as `Bu_OB_2026-01-15T12:00:00`; the chart finds the nearest candle and adjusts the time window. Use the block ID without the position's `_0` bounce suffix. Timestamps without an explicit timezone are interpreted as UTC by this control. Its default visible-candle setting is 150.

The chart draws entry and credited-target event paths for positions with a recorded exit type, with a dashed final segment and cross for stop exits. It is an inspection tool for simulated events, not a rendering of actual exchange executions.

The Markdown documentation renders directly on GitHub. Interactive exported HTML needs to be opened in a browser; GitHub's ordinary file view does not run the chart.

## Backtest analysis reports

The backtest runner automatically writes a combined PDF and five individual PNG figures using [VisualizationEngine](../src/backtest/visualization.py):

| Figure | Purpose |
| --- | --- |
| `01_multi_objective_correlations` | Correlations between swept parameters and fitness metrics. |
| `02_parameter_impact_comparison` | Compare parameter correlation magnitudes across objectives. |
| `03_pareto_front` | Scatter of results to inspect profit, win rate, and performance trade-offs, colored by score. |
| `04_parameter_sensitivity` | Distributions of fitness metrics for each parameter value. |
| `05_top_configurations` | Tables of the top configurations under each available objective. |

The default fitness metrics are `score`, `total_net_profit`, `total_winrate`, `total_performance`, and `average_target_hit`, when present. The default output resolution is 300 DPI. `VisualizationConfig` provides programmatic control of figure sizes, color palette, resolution, and output directory.

The report uses the combined aggregator in the standard runner. Long and short spreadsheets are exported separately but do not receive separate reports automatically. See [backtesting](backtesting.md#scores-and-report-plots) for score definitions and correlation caveats.
