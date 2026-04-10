"""
Telegram client module for sending messages, getting channel names, etc.
"""

import asyncio
import httpx

from src.config import Config

config = Config()


class TelegramClient:
    def __init__(self):
        self._token: str = config.get("TG_BOT_AUTH_TOKEN")
        self._channel_id: str = self._get_channel_id()
        self._async_client = httpx.AsyncClient(proxy=config.get("proxy_server"))

    def _get_channel_id(self):
        if bool(config.get("dev")):
            return config.get("TG_DEV_CHANNEL_ID")
        else:
            return config.get("TG_PROD_CHANNEL_ID")

    async def send_message(
        self, message: str, reply_id: int | None = None
    ) -> int | None:
        """Sends a message to the Telegram channel and returns its ID."""
        payload = {
            "chat_id": self._channel_id,
            "text": message,
            "reply_to_message_id": reply_id,
        }
        url = config.get("telegram_api_endpoint")

        max_retries = int(config.get("telegram_api_max_retries"))
        base_retry_interval = float(config.get("telegram_api_base_retry_interval"))

        for attempt in range(1, max_retries + 1):
            try:
                response = await self._async_client.post(
                    f"{url}bot{self._token}/sendMessage",
                    json=payload,
                )

                response.raise_for_status()
                data = response.json()

                return int(data["result"]["message_id"])

            except KeyError as e:
                print(
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
                    print(f"[telegram] Failed after {max_retries} attempts: {e}")
                    raise

                delay = base_retry_interval * (
                    2 ** (attempt - 1)
                )  # exponential backoff
                print(f"[telegram] Retry {attempt}/{max_retries} in {delay:.1f}s: {e}")
                await asyncio.sleep(delay)

            except httpx.HTTPStatusError as e:
                # Don't retry most HTTP errors (e.g., 400, 401)
                print(
                    f"[telegram] HTTP error: {e.response.status_code} - {e.response.text}"
                )
                raise

            except Exception as e:
                # Unknown errors → fail fast
                print(f"[telegram] Unexpected error: {e}")
                raise

    async def close(self):
        await self._async_client.aclose()
