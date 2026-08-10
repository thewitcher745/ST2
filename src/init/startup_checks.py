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
        channel_infos = await telegram_client.get_channel_names()

        if any(channel_name is None for _, channel_name in channel_infos):
            raise ValueError(
                "Couldn't connect to one or more chats. Check the channel ID values and confirm the bot is an administrator in the chat."
            )

        channel_display = ", ".join(
            f"{channel_name} ({channel_id})"
            for channel_id, channel_name in channel_infos
        )

        if config.dev:
            print(f"\nDEV mode - posting to channels: {channel_display}\n")
            return

        # Production mode - require confirmation
        print(f"\n{'=' * 60}")
        
        if not config.dev:
            print("PRODUCTION MODE")
        else:
            print("DEVELOPMENT/VALIDATION MODE")

        print(f"Target channels: {channel_display}")
        print(f"Primary channel ID: {telegram_client.primary_channel_id}")
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
