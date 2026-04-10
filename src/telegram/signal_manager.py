from typing import cast

from src.logic import LivePosition
from src.logic.blocks.block import Block
from src.telegram import TelegramClient
from .message_template import MessageTemplate


class SignalManager:
    def __init__(self, symbol: str, telegram_client: TelegramClient):
        self._telegram_client = telegram_client
        self._current_blocks: set[Block] = set()
        self._initial_run: bool = (
            True  # Set to true since the first set of signals haven't been sent yet.
        )
        self._symbol = symbol

    async def process_signals(self, updated_blocks: list[Block]):
        """
        Compares the current block ids to the old ones. If there's a new block, sends its
        signal to the channel.

        Args:
            updated_blocks: List of Block objects found in the most recent update (recalc)
        """
        updated_blocks_set = set(updated_blocks)

        # If we're sending the first set of signals,
        if self._initial_run:
            old_blocks_set = set()
            self._initial_run = False
        else:
            old_blocks_set = self._current_blocks

        new_blocks = updated_blocks_set - old_blocks_set
        outdated_blocks = old_blocks_set - updated_blocks_set

        # Cancel the outdated blocks
        for block in outdated_blocks:
            position_to_cancel = cast(LivePosition, block.positions[0])
            if not position_to_cancel.entered:
                assert isinstance(position_to_cancel, LivePosition)

                message_text = "Cancel"
                reply_id = position_to_cancel.telegram_message_id

                await self._telegram_client.send_message(
                    message_text, reply_id=reply_id
                )

                position_to_cancel.signal_canceled = True

        # Send the new blocks
        for block in new_blocks:
            position_to_send = cast(LivePosition, block.positions[0])

            message_text = MessageTemplate.format_signal(position_to_send, self._symbol)
            message_id = await self._telegram_client.send_message(message_text)

            assert isinstance(message_id, int)
            # The +1 is because Cornix re-sends the message with an inline keyboard attached.
            position_to_send.telegram_message_id = message_id + 1
            position_to_send.signal_sent = True

        self._current_blocks = updated_blocks_set
