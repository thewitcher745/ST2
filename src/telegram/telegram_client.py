"""
Telegram client module for sending messages, getting channel names, etc.
"""

import asyncio
import httpx
import logging

from src.config import Config

logger = logging.getLogger("[TelegramClient]")
config = Config()


class TelegramClient:
    def __init__(self):
        self._token: str = config.TG_BOT_AUTH_TOKEN
        self._channel_id: str = self._get_channel_id()
        self._async_client = httpx.AsyncClient(proxy=config.proxy_server)
        self._send_message_lock = asyncio.Lock()
        self._send_message_delay = config.telegram_api_send_message_delay

    def _get_channel_id(self):
        if config.cid is not None:
            return config.cid
        if not config.dev:
            return config.TG_PROD_CHANNEL_ID
        else:
            return config.TG_DEV_CHANNEL_ID

    async def send_message(
        self, message: str, reply_id: int | None = None
    ) -> int | None:
        """
        Sends a message to the Telegram channel and returns its ID. Enforces a timeout between messages
        synced across all tasks.
        """
        payload = {
            "chat_id": self._channel_id,
            "text": message,
            "reply_to_message_id": reply_id,
        }
        url = config.telegram_api_endpoint

        max_retries = config.telegram_api_max_retries
        base_retry_interval = config.telegram_api_base_retry_interval

        # Queue is shared between tasks
        async with self._send_message_lock:
            for attempt in range(1, max_retries + 1):
                try:
                    response = await self._async_client.post(
                        f"{url}bot{self._token}/sendMessage",
                        json=payload,
                    )

                    response.raise_for_status()
                    data = response.json()

                    # Delay between message sends
                    await asyncio.sleep(self._send_message_delay)

                    return int(data["result"]["message_id"])

                except KeyError as e:
                    logger.warning(
                        f"[telegram] Message send failed. Probably an incorrect config: {e}"
                    )
                    raise
                except (
                    httpx.ReadTimeout,
                    httpx.ConnectError,
                    httpx.RemoteProtocolError,
                ) as e:
                    # Retry only network-related errors
                    if attempt == max_retries:
                        logger.error(
                            f"[telegram] Failed after {max_retries} attempts: {e}"
                        )
                        raise

                    delay = base_retry_interval * (
                        2 ** (attempt - 1)
                    )  # exponential backoff
                    logger.warning(
                        f"[telegram] Retry {attempt}/{max_retries} in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)

                except httpx.HTTPStatusError as e:
                    # Don't retry most HTTP errors (e.g., 400, 401)
                    logger.error(
                        f"[telegram] HTTP error: {e.response.status_code} - {e.response.text}"
                    )
                    raise

                except Exception as e:
                    # Unknown errors → fail fast
                    logger.error(f"[telegram] Unexpected error: {e}")
                    raise

    async def close(self):
        await self._async_client.aclose()
