# Strategy: structure and blocks

[Project README](../README.md) · [Documentation index](README.md) · [Positions](positions.md) · [Configuration](configuration.md)

ST2 turns swing structure into price zones, then turns eligible zones into position plans. The same block and position classes are used by backtesting and forward testing, but the latter generates positions only from currently active blocks.

## Structure engines

`structure_engine` selects the detection pipeline in [BlockManager](../src/logic/blocks/block_manager.py).

| Engine | Detection path | Relevant settings |
| --- | --- | --- |
| `pine_replay` | Replays candles sequentially through a Pine-style trend and market-state detector, emitting pivots, MSBs, and block candidates together. | `lag`, `fib_factor` |
| `bulk` | Calculates zigzag pivots, finds four-pivot MSB patterns, then selects base candles from the surrounding legs. | `lag`, `fib_factor`, `zigzag_method` |

The current strategy files select `pine_replay`. If no file defines `structure_engine`, the class fallback is `bulk`. The engines share downstream filters and lifecycle rules, but their pivots, candle selection, and confirmation timing can differ. `zigzag_method` affects only `bulk`.

### Pine replay

[PineBlockDetector](../src/logic/structure/pine_detector.py) maintains rolling high/low windows and two state variables: swing trend and market direction.

1. Compare each high and low with the inclusive rolling extremes of up to `lag` candles. Equal highs/lows qualify.
2. Change swing trend when the opposite rolling extreme is reached, recording a confirmed high or low and its formation index.
3. Test confirmed swings for a market-direction change using `fib_factor`. Guards prevent repeatedly changing market state on the same tracked swings.
4. Select base candles using the detector's tracked pivot ranges, including pivot-index history delayed by `lag` bars. Emit an `OB` and either a `BB` or `MB` on a market-state change.

For an upward market change, the current confirmed high must exceed the previous high by more than `fib_factor * abs(previous_high - current_low)`. The downward case requires the current low to fall below the previous low by more than `fib_factor * abs(current_high - previous_low)`. A change is considered only from the opposite market state and subject to the swing guards.

The detector records block formation at the breaking pivot's confirmation index. Its structural invalidation level comes from the pivot immediately after the broken pivot, even when a market guard delays emission. Preformation checks start at the breaking pivot's candle.

`lag` must be at least 1, and `fib_factor` must be between 0 and 1. The detector implements box creation; ST2's block manager applies activation and invalidation afterward. The original `indicator.pine` mentioned in the detector's docstring is not included in this repository.

### Bulk zigzag

[Zigzag](../src/logic/structure/zigzag.py) compares each candle with the preceding candles in a `lag`-sized window. Use `lag >= 2` for this engine because it takes the maximum/minimum of the window excluding the current candle.

| Rule | `zigzag_method=legacy` | `zigzag_method=indicator` |
| --- | --- | --- |
| New high/low | Strictly greater/less than prior window extremes. | Greater/less than or equal to prior window extremes. |
| Extension of the latest same-type pivot | Requires a strictly more extreme price. | Accepts an equally extreme price. |
| Candle breaks both extremes | Approximates order from candle color: red visits high then low; green/doji visits low then high. | Extends the current leg; when no peak leg exists, selects the low. |

An opposite pivot confirms the preceding pivot. The final unconfirmed pivot is removed from the returned zigzag. Confirmed pivots carry both their candle index and their formation index, plus `HH`, `LH`, `LL`, or `HL` relative to the preceding same-type pivot. Equal highs are labeled `LH`; equal lows are labeled `HL`.

Although any non-`legacy` string currently takes the indicator branch, use `indicator` explicitly.

### Bulk MSBs

[MSBIdentifier](../src/logic/structure/msb.py) scans four consecutive alternating pivots `P0, P1, P2, P3`:

```text
Bullish: low → high P1 → low P2 → high P3
         P3 > P1 + abs(P1 - P2) * fib_factor

Bearish: high → low P1 → high P2 → low P3
         P3 < P1 - abs(P1 - P2) * fib_factor
```

`P1` is the broken level, and `P3` is the breaking pivot. Formation uses `P3`'s confirmation index, rather than the candle where its extreme occurred. Consecutive MSBs in the same direction are suppressed. The two base-candle search legs are `P0 → P1` and `P1 → P2`, inclusive of their endpoints.

## Block types and base candles

Every block uses its base candle's **full high and low**, including wicks. Its direction is bullish or bearish; its type is `OB`, `BB`, or `MB`.

For `bulk`, [BlockFactory](../src/logic/blocks/block_factory.py) selects:

| Block | Bullish base candle | Bearish base candle | Search leg |
| --- | --- | --- | --- |
| `OB` | Last red candle | Last green candle | After the broken pivot: `P1 → P2` |
| `BB` / `MB` | Last green candle | Last red candle | Before the broken pivot: `P0 → P1` |

In the bulk factory, green means `close > open`; dojis fall into the red group. The post-MSB pivot's structure selects `BB` for `LL` or `HH`, otherwise `MB`.

`pine_replay` uses its own pivot-history ranges rather than those two bulk legs. It searches strict red (`open > close`) candles for bullish OBs and bearish BB/MBs, and strict green (`open < close`) candles for bearish OBs and bullish BB/MBs. Dojis are excluded from these searches. Its breaker classification compares the current and previous lows for a bullish transition, or highs for a bearish transition. Consult [the detector](../src/logic/structure/pine_detector.py) when reproducing exact base-candle selection.

Each block records:

| Field | Meaning |
| --- | --- |
| `base_candle_index`, `base_candle_time` | Where the price zone originated. |
| `msb_kline_index` | Candle index of the broken pivot. |
| `low`, `high`, `height` | Zone boundaries and `high - low`. |
| `height_percentage` | `100 * (high - low) / ((high + low) / 2)`. |
| `start_index`, `start_time` | Formation initially, then activation after any waiting rule. |
| `invalidation_price` | Structural level whose breach by a close ends the block. |
| `end_index`, `end_time` | Effective end after invalidation; otherwise `None`. |
| `positions` | Position attempts generated from the block. |

A block ID combines direction, type, and base-candle time, for example `Bu_OB_2026-01-15T12:00:00`. Position IDs add a bounce suffix such as `_0`.

## Candidate filters

Filters are applied before position generation:

| Setting | Effect |
| --- | --- |
| `direction` / `-d` | Keep bullish blocks for `long`, bearish blocks for `short`, or both. |
| `block_types` | Keep a slash-separated selection, for example `OB/BB` or `OB/MB/BB`. |
| `min_block_height_percentage` | Inclusive minimum zone height as a percentage of the midpoint. |
| `max_block_height_percentage` | Inclusive maximum zone height as a percentage of the midpoint. |
| `block_preformation_check_method` | Reject a candidate if a wick touches its configured preformation invalidation level. |

The manager keeps potential blocks separately from accepted blocks. Potential blocks that fail the height filter still participate in structural cancellation propagation. Direction/type and preformation exclusions happen before admission to the potential-block list.

The function named `is_block_formation_valid_vs_price_action` currently always returns `True`; its old candle-piercing check is inactive.

### Preformation checks

The check window starts at the breaking pivot's candle and includes the formation candle. It uses lows for bullish candidates and highs for bearish candidates.

| Value | Rejection condition |
| --- | --- |
| Empty, `none`, `false`, `0`, or `no` | Check disabled; matching of these strings is case-insensitive. |
| `level_block` | Bullish low touches or crosses the block low; bearish high touches or crosses the block high. |
| `level_stoploss` | Wick touches or crosses the initial stop of a theoretical position using the selected stop method and coefficient. |

Touching is sufficient (`<=` for bullish, `>=` for bearish). The stop-based check reflects small-block refinement if the chosen stop method uses it. Its theoretical position is not added to the block's bounce count. Unknown non-disabled values raise `ValueError`.

## Activation: waiting for price to leave the zone

`block_formation_waiting_method` determines when an accepted block starts looking for entries.

| Value | Bullish activation test | Bearish activation test | Effective start |
| --- | --- | --- | --- |
| `price_reach` | Candle high strictly above block high. | Candle low strictly below block low. | The qualifying candle. |
| `price_close` | Candle close strictly above block high. | Candle close strictly below block low. | The next candle, after the qualifying candle has closed. |
| Empty or `none` | Waiting disabled. | Waiting disabled. | Original formation index. |

The search begins at formation. A wick touching the theoretical initial stop ends the activation search **before** that candle. If no qualifying start exists, or the `price_close` delay would reach that stop boundary or the available-data boundary, the block is removed from the accepted and active lists for that calculation. It may become available on a later live recalculation as more candles arrive.

Only `price_reach`, `price_close`, and disabled values are supported. Unlike preformation checking, the string `false` does not disable this setting.

## Invalidation and block lifetime

Structural invalidation is separate from a position stop:

- A bullish block invalidates on a **close strictly below** its structural `invalidation_price`.
- A bearish block invalidates on a **close strictly above** its structural `invalidation_price`.
- The effective end is the following candle, matching the need to wait for a completed close. If that following candle is unavailable, the end is not applied yet.

The level is the pivot immediately after the broken pivot, not necessarily a block edge or a configured stop. The close search starts at the block's base-candle index. When a potential block ends, accepted blocks of the same direction with an earlier or equal start index also have their end brought forward if needed. This propagates the structural change through older zones, including when the newer potential block failed the height filter.

Historical simulation generates positions from all accepted blocks, using their lifetimes to restrict entry searches. Forward testing passes only active blocks into the position manager. A block ending does not itself liquidate an already entered simulated position: targets and stops continue to determine its outcome.

Continue with [positions](positions.md) for target, stop, and bounce behavior, or [forward testing](forward-testing.md) for how block changes affect published signals.
