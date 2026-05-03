"""
Startup validation checks before running the forward test.
"""

from src.telegram import TelegramClient
from src.config import Config

config = Config()


async def confirm_channel():
    """Prompts user to confirm the Telegram channel before proceeding."""
    if config.dry:
        print("\nRunning in DRY mode - no messages will be sent to Telegram\n")
        return

    telegram_client = TelegramClient()

    try:
        channel_name = await telegram_client.get_channel_name()

        if channel_name is None:
            raise ValueError("Couldn't connect to chat. Check the channel ID and confirm the bot is an administrator in the chat.")

        if config.dev:
            print(f"\nDEV mode - posting to channel: {channel_name}\n")
            return

        # Production mode - require confirmation
        print(f"\n{'=' * 60}")
        
        if not config.dev:
            print("PRODUCTION MODE")
        else:
            print("DEVELOPMENT/VALIDATION MODE")

        print(f"Target channel: {channel_name}")
        print(f"Channel ID: {telegram_client._channel_id}")
        print(f"{'=' * 60}\n")

        while True:
            response = (
                input("Proceed with posting to this channel? (y/yes to continue): ")
                .strip()
                .lower()
            )
            if response in ["y", "yes"]:
                print("Confirmed. Starting forward test...\n")
                break
            elif response in ["n", "no"]:
                print("Aborted by user.")
                exit(0)
            else:
                print("Please enter 'y' or 'n'")

    except ValueError:
        raise

    except Exception as e:
        print(f"Error fetching channel info: {e}")
        print("Proceeding anyway...")

    finally:
        await telegram_client.close()
