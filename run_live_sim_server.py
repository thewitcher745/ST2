import asyncio

from src.data_provider import TickWebsocketServer, SimulatedTickProvider
from src.config import Config
from src.data_provider import KLinesData
from src.data_provider.historical import LocalDataProvider

config = Config()
data_provider = LocalDataProvider()

klines_df = data_provider.get_latest_klines("BTCUSDT", config.get("timeframe"))
klines_data = KLinesData(klines_df)


async def main():
    tick_provider = SimulatedTickProvider(klines_data, float(config.get("live_sim_interval")))
    server = TickWebsocketServer(tick_provider)
    print("Server running at", f"{server.host}:{server.port}")
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
