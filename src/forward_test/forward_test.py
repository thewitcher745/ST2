import asyncio
import csv
import logging

from .serializer import FTChartSerializer
from src.telegram.signal_manager import SignalManager
from src.telegram import TelegramClient
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
logger = logging.getLogger("[ForwardTest]")


class ForwardTest:
    def __init__(self, symbols_filename: str):
        self._symbols = self._load_symbols(f"data/symbol_lists/{symbols_filename}")

        logger.info(f"Added symbols {self._symbols}")

        # Shared across all symbols
        self.zigzag = Zigzag()
        self.msb_identifier = MSBIdentifier()
        self.telegram_client = TelegramClient()
        self.tick_provider = BinanceTickProvider(symbols=self._symbols)
        self.sync_manager = DataSyncManager(
            self._symbols, data_provider=BinanceDataProvider
        )
        self.structure_calculator = StructureCalculator()
        self.chart_serializer = FTChartSerializer()

        # One instance per symbol
        self.block_managers: dict[str, BlockManager] = {
            s: BlockManager() for s in self._symbols
        }
        self.position_managers: dict[str, PositionManager] = {
            s: PositionManager() for s in self._symbols
        }
        self.signal_managers: dict[str, SignalManager] = {
            s: SignalManager(symbol=s, telegram_client=self.telegram_client)
            for s in self._symbols
        }
        self._current_price: dict[str, float] = {}

    def _load_symbols(self, filepath: str) -> list[str]:
        with open(filepath, "r") as fs:
            return [row[0].strip().upper() for row in csv.reader(fs)]

    def _remove_symbol(self, symbol: str):
        logger.warning(f"Removing {symbol} from forward test due to consecutive errors")

        self._symbols.remove(symbol)
        self.tick_provider.set_symbols(self._symbols)
        del self.block_managers[symbol]
        del self.position_managers[symbol]

    def _load_klines(self):
        """Loads Binance data, removes faulty symbols."""
        faulty_symbols = self.sync_manager.load_klines()
        for symbol in faulty_symbols:
            self._remove_symbol(symbol)

        if not self._symbols:
            raise RuntimeError("All symbols failed.")

        if faulty_symbols:
            logger.warning(f"Removed faulty symbols: {faulty_symbols}")
            logger.warning(f"Continuing with: {self._symbols}")

    def _calc_for_symbol(self, symbol: str):
        """Recalculates the structure for the given symbol."""
        self.structure_calculator._recalculate(
            self.sync_manager.klines_data[symbol],
            self.zigzag,
            self.block_managers[symbol],
            self.position_managers[symbol],
            self.msb_identifier,
        )

    def _update_current_price(self, symbol: str, current_price: float):
        self._current_price[symbol] = current_price

    async def _process_signals(self, symbol: str):
        """Finds which signals need cancelling and which ones need posting for a given signal."""
        updated_positions_list = [
            p for p in self.position_managers[symbol].positions_aslist if not p.entered
        ]
        current_price = self._current_price[symbol]
        await self.signal_managers[symbol].process_signals(
            updated_positions_list, current_price
        )

    async def run(self) -> None:
        """
        Initiates and runs the forward test loop.
        """
        self._load_klines()
        for symbol in self._symbols:
            self._calc_for_symbol(symbol)
            self._update_current_price(
                symbol, self.sync_manager.klines_data[symbol].close[-1]
            )
            await self._process_signals(symbol)

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
            if isinstance(tick, Exception):
                raise tick

            symbol = tick.symbol

            # If the processing fails, remove the symbol. This generally means a resync failed.
            if not self.sync_manager.process_tick(tick):
                self._remove_symbol(tick.symbol)
                continue

            self._calc_for_symbol(symbol)
            self._update_current_price(symbol, tick.price)
            await self._process_signals(symbol)
            self._write_data()

    async def _get_latest_tick(self, queue: asyncio.Queue[Tick]) -> Tick:
        tick = await queue.get()
        while not queue.empty():
            tick = queue.get_nowait()
        return tick

    def _write_data(self):
        """
        Writes serialized data required for charting to a file every calc_interval seconds.
        """
        agg_blocks_list = {}
        for symbol in self._symbols:
            agg_blocks_list[symbol] = self.block_managers[symbol].all_blocks_aslist
        self.chart_serializer.write(self.sync_manager.klines_data, agg_blocks_list)
