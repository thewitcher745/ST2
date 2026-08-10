"""
Telegram client module for sending messages, getting channel names, etc.
"""

from typing import Any


import asyncio
import httpx
import logging

from src.config import Config

logger = logging.getLogger("[TelegramClient]")
config = Config()


class TelegramClient:
    def __init__(self):
        self._token: str = config.TG_BOT_AUTH_TOKEN
        self._channel_ids: list[str] = self._get_channel_ids()
        self._channel_id: str = self._channel_ids[0]
        self._async_client = httpx.AsyncClient(proxy=config.proxy_server)
        self._send_message_lock = asyncio.Lock()
        self._send_message_delay = config.telegram_api_send_message_delay

    def _get_channel_ids(self) -> list[str]:
        if config.cid is not None:
            runtime_channel_ids = [cid.strip() for cid in config.cid.split(",")]
            runtime_channel_ids = [cid for cid in runtime_channel_ids if cid]
            if runtime_channel_ids:
                return runtime_channel_ids
        if not config.dev:
            return [config.TG_PROD_CHANNEL_ID]
        return [config.TG_DEV_CHANNEL_ID]

    @property
    def primary_channel_id(self) -> str:
        return self._channel_id

    @property
    def channel_ids(self) -> list[str]:
        return self._channel_ids.copy()

    async def _get_channel_name(self, channel_id: str) -> Any | None:
        """Gets the name of the channel associated with a channel ID."""
        url = config.telegram_api_endpoint
        try:
            response = await self._async_client.post(
                f"{url}bot{self._token}/getChat?chat_id={channel_id}",
            )
            response.raise_for_status()
        except Exception:
            return None

        data = response.json()

        if "result" in data:
            result = data["result"]
        else:
            return None

        if "title" in result.keys():
            return result["title"]
        return None

    async def get_channel_name(self) -> Any | None:
        return await self._get_channel_name(self._channel_id)

    async def get_channel_names(self) -> list[tuple[str, Any | None]]:
        channel_names = []
        for channel_id in self._channel_ids:
            channel_names.append((channel_id, await self._get_channel_name(channel_id)))
        return channel_names

    async def send_message(
        self, message: str, reply_id: int | None = None
    ) -> int | None:
        """
        Sends a message to the Telegram channel and returns its ID. Enforces a timeout between messages
        synced across all tasks.
        """
        url = config.telegram_api_endpoint

        max_retries = config.telegram_api_max_retries
        base_retry_interval = config.telegram_api_base_retry_interval
        # Channels to post to are limited to only the primary channel if we are cancelling signals.
        # Otherwise, the message is propagated to all channels
        target_channel_ids = [self._channel_id] if reply_id is not None else self._channel_ids

        # Queue is shared between tasks
        async with self._send_message_lock:
            primary_message_id: int | None = None
            for channel_id in target_channel_ids:
                payload = {
                    "chat_id": channel_id,
                    "text": message,
                    "reply_to_message_id": reply_id,
                }

                for attempt in range(1, max_retries + 1):
                    try:
                        response = await self._async_client.post(
                            f"{url}bot{self._token}/sendMessage",
                            json=payload,
                        )

                        response.raise_for_status()
                        data = response.json()

                        message_id = int(data["result"]["message_id"])
                        if channel_id == self._channel_id:
                            primary_message_id = message_id

                        # Delay between message sends
                        await asyncio.sleep(self._send_message_delay)
                        break

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
                                f"[telegram] Failed after {max_retries} attempts for chat_id {channel_id}: {e}"
                            )
                            raise

                        delay = base_retry_interval * (
                            2 ** (attempt - 1)
                        )  # exponential backoff
                        logger.warning(
                            f"[telegram] Retry {attempt}/{max_retries} in {delay:.1f}s for chat_id {channel_id}: {e}"
                        )
                        await asyncio.sleep(delay)

                    except httpx.HTTPStatusError as e:
                        # Don't retry most HTTP errors (e.g., 400, 401)
                        logger.error(
                            f"[telegram] HTTP error for chat_id {channel_id}: {e.response.status_code} - {e.response.text}"
                        )
                        raise

                    except Exception as e:
                        # Unknown errors → fail fast
                        logger.error(
                            f"[telegram] Unexpected error for chat_id {channel_id}: {e}"
                        )
                        raise

            return primary_message_id

    async def close(self):
        await self._async_client.aclose()
