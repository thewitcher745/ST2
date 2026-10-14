# Architecture and extension points

[Project README](../README.md) · [Documentation index](README.md) · [Configuration](configuration.md)

The strategy is organized into data acquisition, structure detection, block lifecycle, position simulation, and output layers. Both entry points share the core under `src/logic/`.

## Components

| Area | Main components | Responsibility |
| --- | --- | --- |
| [Configuration](../src/config/) | `Config`, `CONFIG_SCHEMA` | Singleton settings, file loading, CLI parsing, type conversion, and run identity. |
| [Historical data](../src/data_provider/historical/) | `DataProvider`, `BinanceDataProvider`, `LocalDataProvider` | Futures OHLC requests and request-specific Feather caching. |
| [Candle containers](../src/data_provider/) | `KLinesData`, `LiveKLinesData` | Fast NumPy-array access, live-candle updates, and tail/full replacement. |
| [Live providers](../src/data_provider/live/) | `Tick`, `AbstractTickProvider`, `BinanceTickProvider`, `SimulatedTickProvider` | Async current-candle updates from Binance or generated intrabar paths. |
| [Structure](../src/logic/structure/) | `Zigzag`, `MSBIdentifier`, `PineBlockDetector`, `Leg` | Pivot and MSB detection; Pine replay also emits candidate formations. |
| [Blocks](../src/logic/blocks/) | `Block`, `BlockFactory`, `BlockManager` | Base-candle zones, filters, activation, structural ends, and active-block tracking. |
| [Positions](../src/logic/position/) | `Position`, `TargetPlan`, `TargetProvider`, `StoplossProvider`, `PositionManager` | Entry/exit plans, quantity weights, and repeat attempts. |
| [Simulation](../src/logic/backtest/) | `PositionSimulator` | Candle event searches and closed-position profit. |
| [Backtest orchestration](../src/backtest/) | `BacktestExecutor`, `ConfigurationGenerator`, `MetricsCalculator`, `ResultsAggregator`, `VisualizationEngine` | Experiments, aggregation, scoring, and exports. |
| [Forward orchestration](../src/forward_test/) | `ForwardTest`, `StructureCalculator`, `DataSyncManager`, `FTChartSerializer` | Live synchronization, recalculation, signal processing, and snapshots. |
| [Telegram](../src/telegram/) | `SignalManager`, `MessageTemplate`, `TelegramClient` | Signal eligibility, saved message identities, formatting, and HTTP delivery. |
| [Visualization](../src/visualization/) | `ChartManager`, `ChartWindow`, `ChartWidget` | Plotly inspection and snapshot-based desktop charts. |
| [Startup](../src/init/) and [logging](../src/logger/) | Bootstrap, cleanup, startup checks, `configure_logging` | Runtime directories, templates, confirmation, and log handlers. |

## Shared calculation contract

```text
OHLC DataFrame
  → KLinesData
  → BlockManager.calculate_structure(data, zigzag, msb_identifier)
      → (zigzag_df, msbs_df) and populated block lists
  → PositionManager.simulate_and_generate_positions(blocks, data)
      → Position objects and optional DataFrame serialization
```

`BlockManager` holds bullish and bearish dictionaries for all accepted blocks, all potential blocks, and active blocks. Potential candidates matter for invalidation propagation even when height filters reject them. Backtests use `all_blocks_aslist`; forward calculations use `all_active_blocks_aslist`.

`PositionManager` holds long and short lists. Each new `Position` normally appends itself to `block.positions`, which supplies the bounce count. Theoretical positions created for filters use `add_to_block=False`.

Pine replay returns `BlockFormation` records alongside pivot/MSB DataFrames. These records preserve the base index, formation index, broken-pivot index, invalidation level, and start of the preformation check. The manager converts them to ordinary `Block` instances before applying shared rules.

## Data contracts

| Object | Main fields |
| --- | --- |
| OHLC DataFrame | `time`, `open`, `high`, `low`, `close`; no volume column is retained. |
| `KLinesData` | NumPy arrays for those columns and `length`. |
| `Tick` | `symbol`, `event_time`, `price`, candle `open/high/low/close`, and `timestamp` for candle open. |
| Zigzag DataFrame | `kline_index`, `time`, `pivot_value`, `pivot_type`, `pivot_formation_index`, `structure`. |
| MSB DataFrame | `direction`, `formation_index`, `pivot_index`, `kline_index`, `break_level`, `leg_before`, `leg_after`. |
| `TargetPlan` | NumPy `prices` and relative `quantity_weights`. |
| Position export | Block ID, direction, entry/exit state, levels, target weights, event timestamps, and P&L. |

Times from Binance are normalized to timezone-naive UTC. Positions serialize timestamps as ISO strings or `None`. Chart candle times use integer nanoseconds. Most candle event times represent opening timestamps of the candle containing the event, not an exact intrabar execution time.

## Storage

| Path | Format | Lifecycle |
| --- | --- | --- |
| `data/symbol_lists/<name>.csv` | Headerless symbol rows | Local input; forward runner selects with `-s`. |
| `data/precisions/precisions.csv` | Headered symbol/decimal-precision table | Tracked input for signal formatting. |
| `data/klines/<run_id>/*.feather` | Feather DataFrames | LocalDataProvider cache; normal forward testing uses direct REST loading instead. |
| `data/state/<run_id>/<SYMBOL>.pickle` | Python pickle | Signal identities and position snapshots; loaded on restart. |
| `data/chart/<run_id>/<SYMBOL>.pack` | MessagePack with NumPy serialization | Latest candles, blocks, and zigzag for the viewer. |
| `logs/<run_id>/forwardtest.log` | Text | UTC log timestamps; daily rotation with 30 backups. |
| `logs/backtest/default/backtest.log` | Text | Standard runner's backtest log; custom executor calls can specify another log run ID. |
| `outputs/<timestamp>/` or selected base | CSV, Excel, JSON, PDF, PNG | Completed experiment exports. |

The bootstrap creates runtime directories and missing templates without overwriting existing files. Cleanup operates on the selected run identity. Use [configuration](configuration.md#run-ids-and-local-directories) to understand how those identities are constructed.

## Extending the strategy

**Add a target plan.** Add a static method to [TargetProvider](../src/logic/position/target_provider.py) that accepts a position and returns a `TargetPlan`. `_build_target_plan()` supplies equal weights when omitted. Return positive weights with one entry per price. Select the method by name in `target_setup_function`. The historical financial calculation uses its weights; Telegram formatting would need a separate change to publish those allocations.

**Add a stop schedule.** Add a static method to [StoplossProvider](../src/logic/position/stoploss_provider.py) that returns one stop per target stage. Index zero is the initial stop. Update `MessageTemplate._create_trailing_setup_string()` if downstream signal text must describe the new behavior; it currently recognizes only fixed and the two breakeven triggers.

**Add a setting.** Add its converter to `CONFIG_SCHEMA`, declare it on `Config`, and provide it in the appropriate file or give it a class fallback. Add a parser option only if it should be configurable from the CLI, bearing in mind that parser defaults overwrite file settings. Update the [reference](configuration.md).

**Add or change a structure engine.** Integrate it through `BlockManager.calculate_structure()` and return the expected chart DataFrames. Reuse the shared candidate filters and lifecycle rules to keep historical and forward paths consistent. For bulk changes, explicitly pass swept `lag` and `fib_factor` into constructors if they must change after import.

**Add a metric.** Calculate it in `MetricsCalculator`. Aggregation includes returned keys automatically; column ordering, score weights, filtered export criteria, and visualization objectives are configured separately in the aggregator and visualization module.

**Use simulated ticks.** `SimulatedTickProvider` generates noisy interpolated intrabar paths constrained by candle OHLC, with randomized high/low placement and no fixed default seed. It is exported for programmatic use, but switching the normal forward workflow requires wiring the provider and initial data flow; changing `live_sim_tick_interval` alone does not select it.

`Config` is initialized during many module imports. Programmatic scripts should arrange CLI arguments and configuration before importing strategy modules, and should avoid importing the top-level backtest runner. The repository currently contains no tracked automated test suite; validate core strategy changes with controlled candle fixtures and event-level inspection before relying on large sweeps.
