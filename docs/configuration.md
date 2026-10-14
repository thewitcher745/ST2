# Configuration reference

[Project README](../README.md) · [Documentation index](README.md) · [Strategy](strategy.md) · [Positions](positions.md)

Configuration is defined by [Config](../src/config/config_provider.py), with allowed names and conversion types in [CONFIG_SCHEMA](../src/config/config_schema.py). The tables below describe values in the shared files and class/CLI fallbacks; most schema entries do not have independent defaults when removed from those files.

## Configuration precedence

Values are loaded from lowest to highest precedence:

1. Class fallbacks, where defined.
2. `.env.config`, or the strategy file selected by `--config` / `--config_file`.
3. `.env.misc`.
4. `.env.secret`.
5. Optional `.env.misc.local`.
6. Parsed CLI arguments, **including parser defaults**.
7. During backtesting, the current parameter combination applied directly to the singleton.

The selected strategy file replaces `.env.config`; it is not layered on top of it. A preset should therefore contain the full strategy configuration. The misc, secret, and local misc files still load from the repository root.

The code uses `dotenv_values()` rather than copying the process environment into `Config`. A shell environment variable alone is not an additional configuration layer, although dotenv interpolation can reference environment values. The object is a singleton, initialized on first use, often during module import. Edit files and restart to reload them.

Three precedence details affect everyday use:

- `timeframe` always becomes the CLI value, whose default is **`15m`**. Pass `-t 1h` when using a one-hour preset.
- `direction` becomes the CLI value, defaulting to `None` (both directions), even if the file contains a direction.
- Runtime flags such as `dry`, `clean`, `shutdown`, and `clear_state` default to `False` and overwrite matching file keys. Enable them using their CLI switches.

Backtest grid values override CLI values for the keys swept, including `timeframe` and `direction` if included.

## Types and accepted values

Unknown file keys raise `AttributeError`. Integer and float conversion errors occur during loading. Boolean strings `true`, `1`, and `yes` are true, case-insensitively; other strings, including an empty assignment, are false. A key without `=` can load as `None`.

Method names and engine names are generally case-sensitive. Use the documented spellings. A quoted `"None"` is still a string; disabled-value interpretation belongs to each specific setting.

## Structure and blocks

The values in this table reflect the root [.env.config](../.env.config).

| Key | Type | Shared value | Meaning |
| --- | --- | --- | --- |
| `structure_engine` | string | `pine_replay` | `pine_replay` or `bulk`; class fallback is `bulk`. |
| `lag` | integer | `9` | Swing lookback length. Pine requires at least 1; use at least 2 for bulk. |
| `fib_factor` | float | `0.33` | Break distance as a fraction of the relevant swing range; Pine validates `0..1`. |
| `zigzag_method` | string | `indicator` | Bulk-only pivot behavior: `indicator` or `legacy`. |
| `timeframe` | string | `15m` | Candle interval; CLI default overrides the file. |
| `block_types` | string | `OB/BB/MB` | Slash-separated block types to include. |
| `min_block_height_percentage` | float | `0.1` | Inclusive minimum `100 * height / midpoint`. |
| `max_block_height_percentage` | float | `3` | Inclusive maximum `100 * height / midpoint`. |
| `refined_block_height_percentage` | float | `1` | Minimum distance basis for target/stop methods that refine small blocks. |
| `block_formation_waiting_method` | string | `price_close` | `price_close`, `price_reach`, or disabled with empty/`none`; class fallback is `price_close`. |
| `block_preformation_check_method` | string | `level_block` | `level_block`, `level_stoploss`, or disabled with empty/`none`/`false`/`0`/`no`; class fallback is `None`. |
| `direction` | string | CLI `None` | `long`, `short`, or `both`; `None` also permits both. Set with `-d`. |

[Strategy](strategy.md) explains the distinct formation, activation, preformation-check, and structural invalidation rules.

## Position plans and capital

| Key | Type | Shared value | Meaning |
| --- | --- | --- | --- |
| `target_setup_function` | string | `small_blocks_refined` | Method name in `TargetProvider`; see [all target methods](positions.md#all-target-methods). |
| `stoploss_setup_function` | string | `small_blocks_refined_trailing_breakeven_t1` | Method name in `StoplossProvider`; see [all stop methods](positions.md#all-stop-methods). |
| `target_coeff` | float | `1` | Multiplier for each target's height-based spacing. |
| `stoploss_coeff` | float | `1.5` | Multiplier for the initial stop distance from entry. |
| `max_bounces` | integer | `2` | Maximum total position attempts from a block, including the initial attempt. |
| `bounce_target_threshold` | integer | `1` | Target number that allows the next bounce; use `1..target_count`. |
| `usdt_per_trade` | float | `100` | Fixed margin amount per simulated position. |
| `leverage` | float | `20` | Notional multiplier and advertised signal leverage. |
| `leverage_type` | string | `cross` | Label in Telegram messages, typically `cross` or `isolated`. |

Target and stop method names are resolved with `getattr`; a typo fails when a position is constructed. There is no comprehensive startup validation of coefficient signs, bounce settings, or combinations of target and stop methods. Use positive coefficients, positive capital and leverage, and a bounce threshold within the selected target count.

## Runtime, network, and retries

Strategy timing values come from `.env.config`; service values come from [.env.misc](../.env.misc).

| Key | Type | Shared value | Meaning |
| --- | --- | --- | --- |
| `startup_n_days` | integer | `30` | Initial history window for the forward test and full resyncs. Does not extend backtest dates. |
| `calc_interval` | float | `10` | Minimum seconds between structure calculations; also used by the chart serializer. |
| `binance_ws_endpoint` | string | See `.env.misc` | Base URL for combined Futures kline streams; provider appends `?streams=...`. |
| `telegram_api_endpoint` | string | See `.env.misc` | Telegram API base URL, including trailing slash. |
| `proxy_server` | string | Class fallback `None` | Optional proxy used by REST, WebSocket, and Telegram clients. Usually set locally. |
| `binance_cache_retry_interval` | float | `5` | Fixed delay in seconds for Binance client initialization and historical fetch retries. |
| `binance_cache_max_retries` | integer | `5` | Maximum attempts for those Binance operations. |
| `binance_cache_resync_buffer` | integer | `5` | Extra candles requested when resyncing live data. |
| `ws_error_retry_interval` | integer | `8` | WebSocket retry delay in seconds. |
| `ws_error_max_retries` | integer | `5` | WebSocket reconnect error threshold; the provider and consumer's current error handling can terminate the run earlier. |
| `telegram_api_max_retries` | integer | `5` | Maximum message-send attempts for retryable network errors. |
| `telegram_api_base_retry_interval` | float | `1` | Base seconds for exponential retry delays: `base * 2^(attempt - 1)`. |
| `telegram_api_send_message_delay` | float | `10` | Delay held after each successful send, under a shared send lock. |
| `live_sim_tick_interval` | float | `2` | Tick spacing in `SimulatedTickProvider`, which is not selected by the normal forward runner. |
| `chart_data_write_interval` | float | `6` | Present in schema and misc file, but currently unused by the serializer; writes use `calc_interval`. |

`StructureCalculator` currently has one shared calculation timestamp across symbols. `calc_interval` therefore throttles the calculator globally rather than maintaining an independent schedule per symbol. See [forward runtime details](forward-testing.md#runtime-details-that-affect-observed-behavior).

## Telegram and local development

| Key | Type | Default/source | Meaning |
| --- | --- | --- | --- |
| `TG_BOT_AUTH_TOKEN` | string | `.env.secret` | Bot token; copy the template before the first run. |
| `TG_DEV_CHANNEL_ID` | string | `.env.secret` | Channel used when `dev=True`, unless `--cid` is supplied. |
| `TG_PROD_CHANNEL_ID` | string | `.env.secret` | Channel used when `dev=False`, unless `--cid` is supplied. |
| `dev` | boolean | Class fallback `False` | Selects the development channel, DEBUG logging, and skips production confirmation after channel lookup. Set in a dotenv file. |
| `validation` | boolean | `.env.misc`: `True` | Append position ID, block start time, and timeframe to Telegram signals. Does not enable development mode or validate performance. |
| `signal_proximity_check` | boolean | `.env.misc`: empty / false | Defer posting setups too far from entry in the unfavorable-to-entry direction. |
| `signal_proximity_check_percent` | integer | `.env.misc`: `2` | Long: defer above `entry * 1.02`; short: defer below `entry * 0.98`, with the default 2. |

Channel selection is `--cid` first, then development or production according to `dev`. There is no CLI `--dev` or automatic sandbox exchange environment.

## CLI reference

The parser is shared by backtesting and forward testing; a parsed option is only effective where the relevant entry point consumes it.

| Option | Default | Behavior |
| --- | --- | --- |
| `-h`, `--help` | — | Print parser help and exit. |
| `--config`, `--config_file PATH` | `.env.config` | Select a complete strategy file. |
| `-s`, `--symbols_filename NAME` | `symbols.csv` | Forward-test CSV filename under `data/symbol_lists/`. Backtest symbols come from the script. |
| `-t`, `--timeframe INTERVAL` | `15m` | Choices: `1m`, `5m`, `15m`, `30m`, `1h`, `4h`. A backtest grid can override it afterward. |
| `-d`, `--direction VALUE` | `None` | `long`, `short`, or `both`. |
| `--cid ID` | `None` | Override both configured Telegram channel choices. |
| `--dry` | `False` | Suppress normal forward signal sends and startup channel lookup; state and files still update. Cancel mode has different behavior. |
| `--clear_logs` | `False` | Clear the current forward run's log directory on startup. |
| `--clear_state` | `False` | Clear the current forward run's saved signal state on startup. |
| `--clear_klines` | `False` | Clear the current forward run's local candle-cache directory on startup. |
| `-c`, `--clean` | `False` | Apply all three cleanup flags. Normal forward startup also clears chart snapshots regardless of flags. |
| `--backtest_output_dir PATH` | `None` | Backtest output base; a simple name is placed under `outputs/`. |
| `--shutdown` | `False` | Shut down the host after backtest exports and visualizations finish. On WSL, invokes Windows shutdown. |
| `-cm`, `--cancel-mode` | `False` | Confirm, then send `Cancel SYMBOL` for every symbol and exit. |

`cancel_mode`, `config_file`, `symbols_filename`, `cid`, `dry`, `clean`, `clear_logs`, `clear_state`, `clear_klines`, `backtest_output_dir`, and `shutdown` are the corresponding schema keys. The forward runner calls the cleanup functions; `run_backtest.py` does not, so cleanup flags do not refresh a backtest cache. `--shutdown` is consumed only by `run_backtest.py`.

Cancel mode bypasses normal channel confirmation and cleanup. Its send loop does **not** honor `--dry`; see [cancel mode](forward-testing.md#cancel-mode).

## Presets

All supplied presets currently select `pine_replay`, `lag=9`, `fib_factor=0.33`, `price_close` waiting, and `level_block` preformation checking. The table records their main differences; linked files contain the full target/stop method choices.

| Strategy file | Timeframe to pass | Blocks | Targets | Target coefficient | Stop coefficient | Max attempts |
| --- | --- | --- | --- | --- | --- | --- |
| [.env.config.base](../env_bat_files/.env.config.base) | `15m` | `OB/BB/MB` | 4 | 1 | 1.5 | 3 |
| [.env.config.crypto](../env_bat_files/.env.config.crypto) | `15m` | `OB/BB/MB` | 4 | 1 | 1.5 | 1 |
| [.env.config.btc_1h](../env_bat_files/.env.config.btc_1h) | `1h` | `OB` | 3 | 1.75 | 1.6 | 1 |
| [.env.config.btc_30m](../env_bat_files/.env.config.btc_30m) | `30m` | `OB/BB` | 1 | 3 | 1.5 | 1 |
| [.env.config.gold_15m](../env_bat_files/.env.config.gold_15m) | `15m` | `MB/BB` | 1 | 3 | 1.5 | 2 |
| [.env.config.gold_30m](../env_bat_files/.env.config.gold_30m) | `30m` | `OB/BB` | 4 | 1.3 | 1.4 | 2 |
| [.env.config.gold_1h](../env_bat_files/.env.config.gold_1h) | `1h` | `OB` | 1 | 3 | 2 | 1 |
| [.env.config.gold_1h_2tp](../env_bat_files/.env.config.gold_1h_2tp) | `1h` | `OB/BB` | 2 | 3 | 2.75 | 2 |
| [.env.config.gold_4h](../env_bat_files/.env.config.gold_4h) | `4h` | `OB/MB/BB` | 4 | 0.9 | 0.9 | 2 |
| [.env.config.silver_1h](../env_bat_files/.env.config.silver_1h) | `1h` | `OB` | 3 | 1.1 | 1.1 | 2 |
| [.env.config.test_dev](../env_bat_files/.env.config.test_dev) | `15m` | `OB/BB/MB` | 4 | 1 | 1.5 | 3 |

The root strategy file allows two attempts, while `.env.config.base` allows three. `test_dev` allows a zero minimum block height and uses five days of startup history, but its name alone does not set `dev=True`.

## Run IDs and local directories

`Config.run_id` is derived from explicitly supplied CLI argument tokens, in a fixed order:

```text
s-<symbol-file-without-.csv>
t-<timeframe>
d-<direction>
cid-<channel-id>
cfg-<configuration-path-with-.env.-and-.config-removed>
```

Present parts are joined with dots; no such arguments produces `default`.

```bash
python run_forward.py --dry -s symbols.csv -t 1h -d long
```

This produces `s-symbols.t-1h.d-long`. Dry mode and cleanup flags are not part of the identity. Explicitly passing the default timeframe still adds a timeframe part. Paths in `--config` retain directory separators in the generated string, which can produce nested storage directories.

Run-scoped storage includes `data/state/<run_id>/`, `data/chart/<run_id>/`, `data/klines/<run_id>/`, and `logs/<run_id>/`. The ID does not hash the file contents, so changing parameters inside a preset does not automatically isolate its state. Use a separate invocation identity or intentionally reset the appropriate state when changing experiments.

Use the space-separated form `--timeframe 1h` and `--config PATH` in reproducible commands. Argparse accepts `--option=value`, but the run-ID scanner only recognizes standalone option tokens and will not include those forms.

Backtest case hashes are a separate concept: [ConfigurationGenerator](../src/backtest/config_generator.py) hashes each combination into the exported `run_id` column. They do not select live state directories.
