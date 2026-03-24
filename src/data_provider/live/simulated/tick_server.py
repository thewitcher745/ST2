import asyncio
import json
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from ..tick import Tick
from ..abstract_tick_provider import AbstractTickProvider


class TickWebsocketServer:
    def __init__(
        self,
        tick_provider: AbstractTickProvider,
        host: str = "127.0.0.1",
        port: int = 5000,
    ):
        self.tick_provider = tick_provider
        self.clients = set()
        self.host: str = host
        self.port: int = port

    def _serialize_tick(self, tick_counter: int, tick: Tick) -> str:
        return json.dumps(
            {
                "counter": tick_counter,
                "timestamp": tick.timestamp.timestamp(),
                "price": tick.price,
                "candle_index": tick.candle_index,
            }
        )

    async def _client_handler(self, connected_client: ServerConnection):
        self.clients.add(connected_client)
        print("Client connected: ", connected_client.id)
        try:
            await connected_client.wait_closed()
        finally:
            self.clients.remove(connected_client)
            print("Client", connected_client.id, "disconnected.")

    async def _broadcast_loop(self):
        tick_counter = 0
        for tick in self.tick_provider.ticks():
            for client in set(self.clients):
                try:
                    await client.send(self._serialize_tick(tick_counter, tick))
                except ConnectionClosed:
                    pass
            tick_counter += 1
            await asyncio.sleep(self.tick_provider.tick_interval)

    async def serve(self):
        async with serve(self._client_handler, self.host, self.port):
            asyncio.create_task(self._broadcast_loop())
            await asyncio.Future()
