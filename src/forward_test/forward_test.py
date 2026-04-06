import asyncio
from datetime import timedelta
import time

from src.data_provider import (
    Tick,
    BinanceDataProvider,
    BinanceTickProvider,
    LiveKLinesData,
)
from src.config import Config
from src.logic import MSBIdentifier, Zigzag, BlockManager, PositionManager
from src.utils import BinanceDataFetchError

config = Config()


class ForwardTest:
    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self.data_provider = BinanceDataProvider()
        self.tick_provider = BinanceTickProvider(symbols=symbols)

        # Stateless — shared across all symbols
        self.zigzag = Zigzag()
        self.msb_identifier = MSBIdentifier()

        # Stateful — one instance per symbol
        self.klines_data: dict[str, LiveKLinesData] = {}
        self.block_managers: dict[str, BlockManager] = {
            s: BlockManager() for s in symbols
        }
        self.position_managers: dict[str, PositionManager] = {
            s: PositionManager() for s in symbols
        }

    def startup(self) -> None:
        faulty_symbols = []
        for symbol in self.symbols:
            try:
                klines_df = self.data_provider.get_latest_klines(
                    symbol,
                    config.get("timeframe"),
                    time_delta=timedelta(days=int(config.get("startup_n_days"))),
                )
                self.klines_data[symbol] = LiveKLinesData(klines_df)
                self._recalculate(symbol)
            except BinanceDataFetchError as e:
                print(f"[startup] Giving up on {symbol} after retries: {e}")
                faulty_symbols.append(symbol)
            except Exception as e:
                print(f"[startup] Failed to initialize {symbol}: {e}")
                faulty_symbols.append(symbol)

        for symbol in faulty_symbols:
            self.symbols.remove(symbol)
            self.tick_provider.set_symbols(self.symbols)
            del self.block_managers[symbol]
            del self.position_managers[symbol]

        if not self.symbols:
            raise RuntimeError("All symbols failed during startup.")

        if faulty_symbols:
            print(f"[startup] Removed faulty symbols: {faulty_symbols}")
            print(f"[startup] Continuing with: {self.symbols}")

    def _recalculate(self, symbol: str) -> None:
        """
        Recalculates the logic of the strategy with a given symbol. The data is fetched from the
        self.klines_data for that symbol
        """
        klines_data = self.klines_data[symbol]
        block_manager = self.block_managers[symbol]
        # position_manager = self.position_managers[symbol]

        zigzag_df = self.zigzag.calculate(klines_data)

        msbs_df = self.msb_identifier.find_all_matches(
            zigzag_df["structure"].tolist(),
            zigzag_df["kline_index"].tolist(),
            zigzag_df["pivot_value"].tolist(),
            zigzag_df["pivot_formation_index"].tolist(),
        )

        block_manager.add_blocks(msbs_df, zigzag_df, klines_data)
        block_manager.update_block_end_times(klines_data)

        print(block_manager.active_blocks)

        # position_manager.add_positions(
        #     [
        #         block
        #         for block in (
        #             block_manager.all_blocks["bullish"]
        #             + block_manager.all_blocks["bearish"]
        #         )
        #     ]
        # )

    async def run(self) -> None:
        self.startup()
        queue: asyncio.Queue[Tick] = asyncio.Queue()

        async def producer():
            async for tick in self.tick_provider.ticks():
                await queue.put(tick)

        asyncio.create_task(producer())

        recalc_total_time = 0.0
        recalc_count = 0

        while True:
            tick = await queue.get()
            # Drain any accumulated ticks, keep only the latest
            while not queue.empty():
                tick = queue.get_nowait()
            self.klines_data[tick.symbol].update(tick)

            t0 = time.perf_counter()
            self._recalculate(tick.symbol)
            recalc_total_time += time.perf_counter() - t0
            recalc_count += 1

            avg_ms = (recalc_total_time / recalc_count) * 1000
            print(
                f"[recalc] count={recalc_count}  avg={avg_ms:.3f}ms  total={recalc_total_time * 1000:.1f}ms"
            )
