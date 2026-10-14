# Getting started

[Project README](../README.md) · [Documentation index](README.md) · [Configuration](configuration.md)

## Install

Use Python 3.13 to match the existing development environment. The desktop chart code uses syntax that requires Python 3.12 or newer. Run all commands from the repository root so relative configuration and data paths resolve correctly.

```bash
python -m venv venv
```

Activate it using the command for your shell:

| Shell | Command |
| --- | --- |
| Windows PowerShell | `.\venv\Scripts\Activate.ps1` |
| Windows Command Prompt | `venv\Scripts\activate.bat` |
| Linux / macOS | `source venv/bin/activate` |

The root [activate.bat](../activate.bat) also activates the Windows environment and opens a command prompt.

```bash
python -m pip install -r requirements.txt
```

[requirements.txt](../requirements.txt) is stored as UTF-16. If you open or regenerate it, preserve a valid text encoding rather than treating the null bytes as dependency names.

The desktop chart viewer additionally needs packages that are currently absent from `requirements.txt`:

```bash
python -m pip install PyQt6 pyqtgraph
```

## Create local files

Copy [the secret template](../src/init/templates/.env.secret.template) to `.env.secret`. On Linux/macOS:

```bash
cp src/init/templates/.env.secret.template .env.secret
mkdir -p data/symbol_lists
```

On PowerShell:

```powershell
Copy-Item src/init/templates/.env.secret.template .env.secret
New-Item -ItemType Directory -Force data/symbol_lists
```

For publishing, fill in the three template keys:

```dotenv
TG_BOT_AUTH_TOKEN="your-bot-token"
TG_DEV_CHANNEL_ID="your-development-channel-id"
TG_PROD_CHANNEL_ID="your-production-channel-id"
```

For `--dry`, the empty strings in the template are sufficient: the client is still constructed, but normal signal messages and channel lookup are skipped. Keep `.env.secret` local; it is ignored by Git.

Create `data/symbol_lists/symbols.csv`:

```csv
BTCUSDT
ETHUSDT
```

Use **one symbol per row, no header, no blank rows**. The loader reads the first column, trims spaces, and converts it to uppercase. `-s` selects a filename inside `data/symbol_lists/`; it does not take a symbol list directly. The [symbol template](../src/init/templates/data/symbol_lists/symbols.csv.template) is another starting point.

The normal forward startup creates missing state, chart, log, and cache directories. Create the credentials and your intended symbol list before running: channel confirmation happens before this bootstrap step.

## Configure a first run

Review [.env.config](../.env.config) and [.env.misc](../.env.misc). The strategy file selects the structure engine, block filters, target and stop methods, bounces, capital, and calculation interval.

Optional `.env.misc.local` is loaded after the shared files and credentials. For development publishing and debug logs:

```dotenv
dev=True
```

`dev=True` selects the development Telegram channel; it still publishes unless `--dry` is present. There is no `--dev` CLI flag. To use a proxy, add `proxy_server="http://proxy-host:port"`; omit it for direct connections. The proxy is passed to the Binance REST, WebSocket, and Telegram clients.

See [configuration precedence](configuration.md#configuration-precedence) before expecting a file setting to override a CLI default.

## Run against live data

```bash
python run_forward.py --dry -s symbols.csv -t 15m
```

Startup loads historical Binance Futures candles including the open candle, calculates the strategy, and then consumes live kline updates. Logs and chart snapshots are written as it runs. Stop the process with `Ctrl+C`.

Dry mode suppresses normal Telegram sends but **still saves signal state**, marking simulated sends as sent. When moving to publishing, start with a different [run ID](configuration.md#run-ids-and-local-directories), or intentionally reset that run's state with `--clear_state`. Resetting state forgets previous posts, so previously eligible setups may be sent again.

For actual publishing, fill in `.env.secret`, give the bot permission to post in the selected channel, and run without `--dry`. Production mode asks you to confirm the resolved channel. [Forward testing](forward-testing.md) explains startup, signal eligibility, and cancellation in detail.

## Use a preset

Presets live in [env_bat_files](../env_bat_files/). For example:

```bash
python run_forward.py --dry --config env_bat_files/.env.config.btc_1h -s symbols.csv -t 1h
```

Supply `-t` explicitly: without it, the parser applies `15m` after loading the file, including a preset that says `1h`. A preset selects strategy parameters; the CSV still selects the symbols. The [preset reference](configuration.md#presets) lists the available files.

## Run a backtest or open charts

For historical experiments, first configure dates, symbols, and a small grid in [run_backtest.py](../run_backtest.py), then run:

```bash
python run_backtest.py --backtest_output_dir first_run
```

The [backtesting guide](backtesting.md) explains the grid and exports. Its symbol list comes from the script, rather than `-s`.

While a forward test is running, launch the viewer in another activated terminal:

```bash
python chart.py
```

Select the run and symbol. The viewer needs `data/chart/` and at least one run directory; let forward testing create these first. See [charts](charts.md) for controls and HTML charts, or [troubleshooting](troubleshooting.md) for setup issues.
