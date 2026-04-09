import asyncio

from .calculator import StructureCalculator
from .data_sync_manager import DataSyncManager
from src.data_provider import (
    Tick,
    BinanceDataProvider,
    BinanceTickProvider,
)
from src.config import Config
from src.logic import MSBIdentifier, Zigzag, BlockManager, PositionManager

config = Config()


class ForwardTest:
    def __init__(self, symbols: list[str]):
        self._symbols = symbols

        # Stateless — shared across all symbols
        self.zigzag = Zigzag()
        self.msb_identifier = MSBIdentifier()
        self.tick_provider = BinanceTickProvider(symbols=symbols)
        self.sync_manager = DataSyncManager(symbols, data_provider=BinanceDataProvider)
        self.structure_calculator = StructureCalculator()

        # Stateful — one instance per symbol
        self.block_managers: dict[str, BlockManager] = {
            s: BlockManager() for s in symbols
        }
        self.position_managers: dict[str, PositionManager] = {
            s: PositionManager() for s in symbols
        }

    def _load_klines(self):
        """Loads Binance data, removes faulty symbols."""
        faulty_symbols = self.sync_manager.load_klines()
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

    def _calc_for_symbol(self, symbol: str):
        self.structure_calculator._recalculate(
            self.sync_manager.klines_data[symbol],
            self.zigzag,
            self.block_managers[symbol],
            self.position_managers[symbol],
            self.msb_identifier,
        )

    async def run(self) -> None:
        """
        Initiates and runs the forward test loop.
        """
        self._load_klines()
        for symbol in self._symbols:
            self._calc_for_symbol(symbol)
        await self._start_live_loop()

    async def _start_live_loop(self) -> None:
        """
        The tick production and consumption parent method.
        """
        queue: asyncio.Queue[Tick] = asyncio.Queue()
        asyncio.create_task(self._produce_ticks(queue))
        await self._consume_ticks(queue)

    async def _produce_ticks(self, queue: asyncio.Queue[Tick]) -> None:
        try:
            async for tick in self.tick_provider.ticks():
                await queue.put(tick)
        except Exception as e:
            await queue.put(e)  # type: ignore

    async def _consume_ticks(self, queue: asyncio.Queue[Tick]) -> None:
        while True:
            tick = await self._get_latest_tick(queue)
            self.sync_manager.process_tick(tick)

            self._calc_for_symbol(tick.symbol)

    async def _get_latest_tick(self, queue: asyncio.Queue[Tick]) -> Tick:
        tick = await queue.get()
        while not queue.empty():
            tick = queue.get_nowait()
        return tick
