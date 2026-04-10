import asyncio
from src.forward_test import ForwardTest
from src.bootstrap import run_bootstrap


async def main():
    # Initializes the folder structure and necessary files.
    run_bootstrap()

    forward_test = ForwardTest(symbols=["BTCUSDT"])
    await forward_test.run()


if __name__ == "__main__":
    asyncio.run(main())
