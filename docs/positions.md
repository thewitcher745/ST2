# Positions, targets, stops, and bounces

[Project README](../README.md) · [Documentation index](README.md) · [Strategy](strategy.md) · [Backtesting](backtesting.md)

The [Position](../src/logic/position/position.py) class turns a block into an entry, target plan, and stop schedule. [PositionManager](../src/logic/position/position_manager.py) simulates these plans and decides whether the block can generate another attempt.

## Entry and sizing

| Block direction | Position | Entry | Historical touch test |
| --- | --- | --- | --- |
| Bullish | Long | Block high | Candle low `<= entry` |
| Bearish | Short | Block low | Candle high `>= entry` |

Entry searches begin at block activation, or the previous attempt's qualifying target index for a bounce. They extend through the effective block-end candle when one exists, otherwise through available data. The simulator fills at the configured entry level, including when a candle gaps across it.

Capital settings are fixed per simulated position:

```text
notional = usdt_per_trade * leverage
quantity = notional / entry
```

`usdt_per_trade` is the margin amount used for profit calculations. It is **not** a fixed amount lost if stopped out; loss depends on price distance and leverage. `leverage_type` is used in Telegram text and does not change the simulator's arithmetic. There is no shared account balance or capital reservation across concurrent positions.

## Target distances and small-block refinement

Let `H = block.high - block.low` and `M = (block.high + block.low) / 2`.

Default target methods use `H`. Refined methods substitute a minimum distance base for blocks below `refined_block_height_percentage`:

```text
refinement_height = M * refined_block_height_percentage / 100
effective_height = refinement_height if 0 <= block.height_percentage < threshold
                   else H

Long target i  = entry + i * effective_height * target_coeff
Short target i = entry - i * effective_height * target_coeff
```

Targets are numbered from 1. Refinement changes planned distances; it does not resize the zone or bypass minimum/maximum block-height filters. Target and stop methods select refinement independently, so a configuration can use actual-height targets and refined-height stops, or the reverse.

## All target methods

Set `target_setup_function` to a method in [TargetProvider](../src/logic/position/target_provider.py).

| Method | Targets | Height basis | Exit shares |
| --- | --- | --- | --- |
| `default` | T1–T4 | Actual block height | 25% each |
| `default_t1_only` | T1 | Actual block height | 100% at T1 |
| `default_t1_t2_only` | T1–T2 | Actual block height | 50% each |
| `default_t1_t2_t3_only` | T1–T3 | Actual block height | One third each |
| `default_t1_half_rest_even` | T1–T4 | Actual block height | 50% at T1; one sixth at each later target |
| `small_blocks_refined` | T1–T4 | Refined minimum height | 25% each |
| `small_blocks_refined_t1_only` | T1 | Refined minimum height | 100% at T1 |
| `small_blocks_refined_t1_t2_only` | T1–T2 | Refined minimum height | 50% each |
| `small_blocks_refined_t1_t2_t3_only` | T1–T3 | Refined minimum height | One third each |
| `small_blocks_refined_t1_half_rest_even` | T1–T4 | Refined minimum height | 50% at T1; one sixth at each later target |

Target methods return a `TargetPlan` containing `prices` and `quantity_weights`. Weights are relative: `[3, 1, 1, 1]` normalizes to `[1/2, 1/6, 1/6, 1/6]`. Equal-share plans use all-one weights. Before calculating the financial outcome of an exited position, the simulator requires a nonempty weight array, one weight per target, and positive weights.

These weights affect **backtest profit calculations**. Telegram messages list target prices but do not serialize target quantity percentages; configure downstream allocation separately if you want execution to match weighted simulations.

## All stop methods

Set `stoploss_setup_function` to a method in [StoplossProvider](../src/logic/position/stoploss_provider.py).

```text
Long initial stop  = entry - effective_height * stoploss_coeff
Short initial stop = entry + effective_height * stoploss_coeff
```

The stop array is a schedule indexed by the number of targets already reached: `stoplosses[0]` is active before T1, `stoplosses[1]` after T1, and so on. It is normally the same length as the target array.

| Method | Initial distance basis | Later behavior |
| --- | --- | --- |
| `default` | Actual block height | Keep the initial stop. |
| `trailing_breakeven_t1` | Actual block height | Move to entry after T1. |
| `trailing_breakeven_t2` | Actual block height | Move to entry after T2. |
| `small_blocks_refined_no_trailing` | Refined minimum height | Keep the initial stop. |
| `small_blocks_refined_trailing_breakeven_t1` | Refined minimum height | Move to entry after T1. |
| `small_blocks_refined_trailing_breakeven_t2` | Refined minimum height | Move to entry after T2. |

For four targets, the schedules are:

```text
Fixed:           [S0, S0, S0, S0]
Breakeven at T1: [S0, entry, entry, entry]
Breakeven at T2: [S0, S0, entry, entry]
```

These are discrete breakeven schedules; they do not continuously trail market price. A breakeven trigger has an effect only if quantity remains after that target. Use T2 stop methods with at least two targets: their current implementation creates two initial stop slots even for a one-target plan.

## Example

Consider a bullish block from `99` to `100`, so entry is `100`, height is `1`, and midpoint is `99.5`. With `target_coeff=1`, four default targets, `stoploss_coeff=1.5`, and breakeven at T1:

```text
Targets: 101, 102, 103, 104
Stops:   98.5 before T1, then 100
```

With `usdt_per_trade=100` and `leverage=20`, notional is `2,000` and quantity is `20`.

| Outcome | Equal quarters | T1 half, rest even |
| --- | --- | --- |
| Initial stop before T1 | `-30` USDT / `-30%` of margin | `-30` USDT / `-30%` |
| T1, then breakeven stop | `+5` USDT / `+5%` | `+10` USDT / `+10%` |
| All four targets | `+50` USDT / `+50%` | `+40` USDT / `+40%` |

A stop at entry can still produce a profitable trade because some quantity has already exited at targets. With a fixed stop, hitting T1 can still leave the overall trade negative when the remaining quantity is stopped.

For a smaller block from `99.8` to `100`, actual height is `0.2` and midpoint is `99.9`. A refinement threshold of `1` means the refined height is `0.999`; refined target and stop methods use that distance base instead of `0.2`.

## Historical event processing

[PositionSimulator](../src/logic/backtest/position_simulator.py) performs these steps:

1. Find the first entry touch inside the allowed entry window.
2. Search favorable highs or lows for target touches in order; several targets may share a candle.
3. Build windows between entry and target events and check the appropriate stop for each stage.
4. Trim target events that occurred after a stop and record the exit.
5. Calculate profit only for exited positions.

When entry, targets, and stops overlap in one candle, candle color is used to approximate event ordering. Green means `close > open`; dojis follow the non-green branch. These checks approximate intrabar movement from OHLC data; they do not reconstruct actual ticks. [Backtesting assumptions](backtesting.md#simulation-assumptions-and-implementation-limits) describes the limits.

An effective block end restricts new entries, but target and stop searches for an entered position continue through the remaining dataset. A structural block cancellation does not force an exit.

## Bounces and repeat entries

`max_bounces` counts **all attempts, including the initial position**. Thus `1` allows only the initial attempt and `2` allows one additional attempt.

After simulating an attempt, the manager stops generating positions for that block if:

- `highest_target < bounce_target_threshold`;
- the entered position exited as `STOPLOSS_0`;
- the number of generated positions has reached `max_bounces`.

Otherwise, it creates the next position with the same entry, targets, and stop setup. The next entry search starts at the candle index of the configured threshold target. This is the target event, rather than the prior position's exit, so attempts can overlap. An attempt does not need to have fully exited before another is generated. The search also includes the threshold candle itself.

Use `max_bounces >= 1` and `1 <= bounce_target_threshold <= number_of_targets`. These constraints are not comprehensively validated at startup. The initial position is created even if `max_bounces` is zero.

## Recorded outcomes and profit

| Field | Meaning |
| --- | --- |
| `entered`, `exited` | Whether an entry and then a terminal exit were found. |
| `highest_target` | Number of targets credited before the recorded stop or final target. |
| `exit_type` | `FULL_TARGET`, `STOPLOSS_0`, `STOPLOSS_1`, etc.; otherwise `None`. |
| `entry_time`, `exit_time` | Candle opening timestamps for the events. |
| `target_times`, `target_indices` | Credited target event locations. |
| `stop_time`, `stop_price` | Stop event details, when stopped. |
| `net_profit` | Simulated profit in USDT, recorded only for an exited position. |
| `percent_profit` | `100 * net_profit / usdt_per_trade`. |

The financial calculation assigns each target its normalized quantity. Credited targets exit at their target prices; remaining quantity exits at `stop_price`. Long profit is exit proceeds minus entry notional; short profit reverses that subtraction.

No fees, funding, slippage, liquidation, or compounding are modeled. Open positions remain at zero recorded profit rather than being marked to market. The `full_target` field is serialized but currently never updated from its initial `False`; use `exit_type == "FULL_TARGET"` to identify complete target exits.

Continue with [backtesting](backtesting.md) for aggregate metrics, or [forward testing](forward-testing.md) for signal eligibility and posting.
