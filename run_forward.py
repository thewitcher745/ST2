import asyncio

from src.forward_test import ForwardTest
from src.init import run_bootstrap, clear_previous, confirm_channel, confirm_cancel_mode
from src.logger.logger_config import configure_logging
from src.config import Config

# Initializes the config
config = Config()


async def main():
    if config.cancel_mode:
        confirm_cancel_mode()
        forward_test = ForwardTest(symbols_filename=config.symbols_filename)
        await forward_test.run()
        return
    await confirm_channel()
    
    # Clears the state and logs folders if their flags are set.
    clear_previous()

    # Initializes the folder structure and necessary files.
    run_bootstrap()

    # Configures logger formatters
    configure_logging()

    forward_test = ForwardTest(symbols_filename=Config().symbols_filename)
    await forward_test.run()


if __name__ == "__main__":
    asyncio.run(main())
