# ST2 documentation

[Project README](../README.md)

These guides describe the implementation in this repository, including differences between historical simulation, live signal publishing, and desktop visualization.

## Start here

For a first run, follow [getting started](getting-started.md), then choose [backtesting](backtesting.md) or [forward testing](forward-testing.md).

To understand or change the strategy, read [strategy](strategy.md), [positions](positions.md), and the [configuration reference](configuration.md). To inspect its behavior, use the [chart guide](charts.md).

## Guides

| Page | What it explains |
| --- | --- |
| [Getting started](getting-started.md) | Environment setup, credentials, symbol lists, first runs, and presets. |
| [Strategy](strategy.md) | `pine_replay` and `bulk`, swing labels, MSB confirmation, OB/BB/MB selection, block timing, and filters. |
| [Positions](positions.md) | Entries, ten target methods, six stop methods, partial exits, sizing, profit math, and bounce rules. |
| [Configuration](configuration.md) | File precedence, all schema keys, CLI flags, preset settings, and directory identities. |
| [Backtesting](backtesting.md) | Parameter grids, data cache, output files, metric definitions, scoring, and assumptions. |
| [Forward testing](forward-testing.md) | Candle updates and resyncs, Telegram setup, posting and cancellation rules, persistence, and cancel mode. |
| [Charts](charts.md) | Snapshot viewer controls, Plotly HTML generation, and backtest report figures. |
| [Architecture](architecture.md) | Components, data contracts, execution flow, storage formats, and extension points. |
| [Troubleshooting](troubleshooting.md) | Diagnosis of timeframe overrides, missing signals, stale state, connection errors, empty reports, and chart setup. |

## Terminology

| Term | Meaning in ST2 |
| --- | --- |
| Kline | An OHLC candle with an opening timestamp. |
| Pivot | A swing high (`1`) or swing low (`-1`), with a separate index recording when it was confirmed. |
| HH / LH / LL / HL | Higher high, lower high, lower low, and higher low relative to the previous pivot of the same type. |
| MSB | Market structure break, confirmed by the selected structure engine. |
| OB / BB / MB | Order block, breaker block, and mitigation block. |
| Base candle | The historical candle whose full high/low defines a block's vertical zone. |
| Formation | The engine's confirmation point for a candidate block. |
| Activation | The point at which a block can begin generating entries, after any waiting rule. |
| Invalidation | A close beyond the structural invalidation level; it ends the block and can end older blocks of the same direction. |
| Bounce | A position attempt from a block. The initial attempt has `bounce_id=0`. |
| Run ID | The CLI-derived identity used for local state, logs, chart snapshots, and candle caches. |
| Case ID | A 12-character hash identifying one parameter combination in a backtest export. |

Return to the [project README](../README.md) for the overview and entry-point commands.
