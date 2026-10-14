# Troubleshooting

[Project README](../README.md) · [Documentation index](README.md) · [Configuration](configuration.md)

## A preset runs on 15-minute candles

The parser's default `timeframe=15m` is applied after the file. Pass the intended interval explicitly:

```bash
python run_forward.py --dry --config env_bat_files/.env.config.btc_1h -s symbols.csv -t 1h
```

In backtesting, a `timeframe` entry in `params_range_dict` overrides both the file and CLI. See [precedence](configuration.md#configuration-precedence).

## A file setting appears to be ignored

Check `.env.misc`, `.env.secret`, and `.env.misc.local` for later overrides. Parsed CLI defaults overwrite runtime keys even when you did not supply a switch. For example, `shutdown=True` in a strategy file becomes false unless `--shutdown` is supplied. Set `dev=True` in a dotenv file; no `--dev` option exists.

Settings reload on process restart because `Config` is a singleton. The bulk zigzag and MSB classes also capture their default `lag` and `fib_factor` at import time; see [backtest execution](backtesting.md#execution-flow).

## Startup cannot find credentials or a symbol file

Run from the repository root. Copy [the secret template](../src/init/templates/.env.secret.template) to `.env.secret` before publishing or a dry forward run, and create `data/symbol_lists/<filename>.csv`. Normal channel confirmation precedes bootstrap, and cancel mode bypasses bootstrap entirely.

Use one symbol per row, no header and no blank rows. The loader reads the first column of every row. `-s btc.csv` means `data/symbol_lists/btc.csv`; a market name in that argument is not interpreted as a symbol directly.

## Telegram channel confirmation fails

Verify the token and the selected channel ID, the bot's channel permissions, and network/proxy connectivity. `--cid` overrides both development and production IDs. Otherwise `dev` selects the channel. A preset named `test_dev` does not enable development mode by itself.

Use `--dry` for normal forward testing without channel lookup or signal delivery. This does not make cancel mode dry; its cancellation loop still sends after confirmation.

## Binance data loading or WebSocket connection fails

Check that the symbol is available on Binance Futures and that the configured endpoint and optional local proxy are reachable. The provider uses Futures klines; a symbol mentioned in the Telegram exchange list is not necessarily a valid Binance Futures data symbol.

Historical requests and client initialization use the Binance retry settings. Invalid symbol/interval responses are treated as permanent errors. Forward initialization removes faulty symbols and stops if none remain. WebSocket errors can propagate to the consumer before all listener retries finish; inspect logs and restart after fixing the connection.

Logs use UTC timestamps. Standard paths are `logs/<run_id>/forwardtest.log` and `logs/backtest/default/backtest.log`.

## No signals are posted

Check the conditions in this order:

1. `--dry` suppresses normal sends; `dev=True` does not.
2. Saved state may already contain the position ID, including state written during a dry run.
3. The selected structure engine must have enough history to detect a confirmed break.
4. Direction, block-type, height, and preformation filters may reject the block.
5. With `price_close`, price must close beyond the zone, then a following candle must exist before activation. A wick touching the theoretical initial stop can end the activation search first.
6. A position entered before the signal manager's launch is omitted. The current-price proximity and initial-stop checks can defer other positions.
7. Multi-symbol calculations share one interval timer, so a symbol can miss recalculation opportunities.

Enable `dev=True` for DEBUG logging and inspect the [chart viewer](charts.md) to compare zone boundaries and activation time. Increasing `startup_n_days` can expose earlier swings, but also changes the detector's input history. See the [strategy](strategy.md) and [signal lifecycle](forward-testing.md#recalculation-and-signal-lifecycle) guides.

## A dry run affects later publishing, or old signals reappear

Dry runs write sent-signal state, and `--dry` is not included in the run identity. Choose a distinct invocation identity for development, or intentionally use `--clear_state` for the affected run when starting publishing. Clearing state forgets prior sends and can cause eligible setups to be posted again; it does not cancel existing Telegram messages.

Editing a preset's contents does not change the run ID. Explicit arguments such as symbol filename, timeframe, direction, channel, and configuration path control it. Use standalone argument tokens rather than `--option=value` when you want them included. See [run IDs](configuration.md#run-ids-and-local-directories).

## Cancellations do not reply to the expected message

Normal cancellations store the Telegram send result plus one, assuming a Cornix repost. Check whether that convention matches your channel. Entered positions are deliberately skipped, and their status is inferred from local candle simulation. State snapshots are saved on send/cancel mapping changes, so a restart may load an older status snapshot.

Bulk `--cancel-mode` sends `Cancel SYMBOL` messages instead of replying to stored message IDs. It does not clear state and does not honor `--dry`. See [forward testing](forward-testing.md#cancel-mode).

## Backtest output is empty or a column lookup fails

Inspect the log for skipped symbols and calculation failures. If every symbol fails or no positions exist, the runner can lack a `type` column for long/short slicing or metric columns for filtered exports. Verify a single valid symbol with a small grid and enough history first.

Unknown configuration keys raise `AttributeError`; invalid method names fail on position construction. Keep `bounce_target_threshold` between 1 and the number of targets, and `max_bounces` at least 1. Use bulk `lag >= 2`, or Pine `lag >= 1` and `fib_factor` within `0..1`.

No `filtered_results.xlsx` is expected when no case passes all export filters. Long and short CSVs are not produced by the standard runner; their exports are Excel files. See [output files](backtesting.md#output-paths-and-files).

## Profit, win rate, or drawdown differs from expectations

The simulator uses fixed margin times leverage, normalized target quantities, and only closed-position profit. Fees, funding, slippage, liquidation, and shared portfolio capital are absent. A target hit alone does not guarantee a positive final trade, and bounces can overlap.

Drawdown is a negative USDT amount, not a percentage. Monthly groups use entry time and generally exclude months without closed trades. The cumulative P&L curve is not seeded with starting capital. Inspect [position calculations](positions.md) and [metric definitions](backtesting.md#metric-definitions) before comparing to an external report.

## Charts fail to open or appear stale

Install `PyQt6` and `pyqtgraph` in the active environment; they are absent from the current requirements file. Use Python 3.12 or newer for the chart source, with 3.13 matching the existing environment. A GUI-capable desktop/display is required for `chart.py`.

Start a forward test before the viewer so `data/chart/` and a run directory exist. Select the right run and symbol. The viewer polls every two seconds, but snapshots currently use `calc_interval`, not `chart_data_write_interval`. Run choices are captured on viewer startup, and snapshot writes start after live tick processing. A blocked live loop or failed connection can leave the displayed data unchanged.

`chart.py` shows snapshots; it does not generate a historical HTML chart. For HTML export and browser zoom controls, use [ChartManager](charts.md#interactive-html-charts).
