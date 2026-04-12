import asyncio

from src.forward_test import ForwardTest
from src.init import run_bootstrap, clear_previous
from src.logger.logger_config import configure_logging


async def main():
    # Clears the state and logs folders if their flags are set.
    clear_previous()

    # Configures logger formatters
    configure_logging()

    # Initializes the folder structure and necessary files.
    run_bootstrap()

    forward_test = ForwardTest(symbols=["BTCUSDT"])
    await forward_test.run()


if __name__ == "__main__":
    asyncio.run(main())
