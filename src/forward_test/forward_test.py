import asyncio
from datetime import timedelta

from src.data_provider import (
    Tick,
    BinanceDataProvider,
    BinanceTickProvider,
    LiveKLinesData,
)
from src.config import Config
from src.logic import MSBIdentifier, Zigzag, BlockManager, PositionManager
from src.utils import BinanceDataFetchError
from src.utils import convert_timeframe_to_timedelta

config = Config()


class ForwardTest:
    def __init__(self, symbols: list[str]):
        self._symbols = symbols
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

    def _load_klines(self) -> None:
        faulty_symbols = []
        for symbol in self._symbols:
            try:
                klines_df = self.data_provider.get_latest_klines(
                    symbol,
                    config.get("timeframe"),
                    time_delta=timedelta(days=int(config.get("startup_n_days"))),
                    include_live_candle=True,
                )
                self.klines_data[symbol] = LiveKLinesData(klines_df)
                print(
                    f"[startup] Fetched {self.klines_data[symbol].length} KLines for symbol {symbol}"
                )
            except BinanceDataFetchError as e:
                print(f"[startup] Giving up on {symbol} after retries: {e}")
                faulty_symbols.append(symbol)
            except Exception as e:
                print(f"[startup] Failed to initialize {symbol}: {e}")
                faulty_symbols.append(symbol)

        for symbol in faulty_symbols:
            self._symbols.remove(symbol)
            self.tick_provider.set_symbols(self._symbols)
            del self.block_managers[symbol]
            del self.position_managers[symbol]

        if not self._symbols:
            raise RuntimeError("All symbols failed during startup.")

        if faulty_symbols:
            print(f"[startup] Removed faulty symbols: {faulty_symbols}")
            print(f"[startup] Continuing with: {self._symbols}")

    def _initial_calculate(self):
        for symbol in self._symbols:
            self._recalculate(symbol)

    def _resync_data(self, tick: Tick) -> None:
        """
        Resyncs the KLines with the server by fetching a number of the most recent candles.
        """
        # print("------RESYNC------")
        # print(f"[resync] Incoming tick timestamp is {tick.timestamp} (vs. {self.klines_data[tick.symbol].live_candle_time} on local)")

        symbol = tick.symbol

        # 1. Find the amount of time that has passed since the last "closed" candle of the dataset.
        time_elapsed: timedelta = (
            tick.timestamp - self.klines_data[symbol].last_closed_time
        )

        # 2. Find how many klines we need to fetch, and add a fixed buffer to it for safety.
        timeframe = config.get("timeframe")
        candle_timedelta = convert_timeframe_to_timedelta(timeframe)
        # The resync buffer is a safety margin we add to each fetch to mend any possible inconsistency in the data
        resync_buffer = int(config.get("binance_cache_resync_buffer"))
        n_klines = int(time_elapsed / candle_timedelta) + resync_buffer
        # print(f"[resync] {n_klines} candles to fetch.")
        # 3. Resync the KLinesData using the data just fetched.
        incoming_klines_data = self.data_provider.get_latest_klines(
            symbol,
            timeframe,
            limit=n_klines,
            most_recent=True,
            include_live_candle=True,
        )
        self.klines_data[symbol].replace(incoming_klines_data, partial=True)
        # print(
        #     f"[resync] Fetched {len(incoming_klines_data)} candles and resynced data."
        # )

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

    async def run(self) -> None:
        """
        Initiates and runs the forward test loop.
        """
        self._load_klines()
        self._initial_calculate()
        await self._start_live_loop()

    async def _start_live_loop(self) -> None:
        """
        The tick production and consumption parent method.
        """
        queue: asyncio.Queue[Tick] = asyncio.Queue()
        asyncio.create_task(self._produce_ticks(queue))
        await self._consume_ticks(queue)

    async def _produce_ticks(self, queue: asyncio.Queue[Tick]) -> None:
        async for tick in self.tick_provider.ticks():
            await queue.put(tick)

    async def _consume_ticks(self, queue: asyncio.Queue[Tick]) -> None:
        while True:
            tick = await self._get_latest_tick(queue)
            # If we are still in the same candle, update it
            if tick.timestamp == self.klines_data[tick.symbol].live_candle_time:
                self.klines_data[tick.symbol].update(tick)
            # Otherwise, resync the last few candles with the server
            else:
                self._resync_data(tick)
            self._recalculate(tick.symbol)

    async def _get_latest_tick(self, queue: asyncio.Queue[Tick]) -> Tick:
        tick = await queue.get()
        while not queue.empty():
            tick = queue.get_nowait()
        return tick
