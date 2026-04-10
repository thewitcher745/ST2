from pathlib import Path
from typing import cast
import pickle

from src.logic import LivePosition
from src.logic.blocks.block import Block
from src.telegram import TelegramClient
from .message_template import MessageTemplate

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class SignalManager:
    def __init__(self, symbol: str, telegram_client: TelegramClient):
        self._telegram_client = telegram_client
        self._current_blocks: set[Block] = set()
        self._initial_run: bool = (
            True  # Set to true since the first set of signals haven't been sent yet.
        )
        self._symbol = symbol
        self._state_filepath = BASE_DIR / "data" / "state" / f"{symbol}.pickle"

        self._load_state()

    def _save_state(self):
        """Save the current state to disk."""
        state = {
            "current_blocks": self._current_blocks,
            "initial_run": self._initial_run,
        }
        with open(self._state_filepath, "wb") as f:
            pickle.dump(state, f)

    def _load_state(self):
        """Load state from disk if it exists."""
        try:
            with open(self._state_filepath, "rb") as f:
                state = pickle.load(f)
                self._current_blocks = state["current_blocks"]
                self._initial_run = state["initial_run"]
            print(f"[state] Loaded state for {self._symbol}")
        except FileNotFoundError:
            print(f"[state] No saved state found for {self._symbol}, starting fresh")

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

        # Only save the state if anything changes.
        _save_state_required = False

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
                _save_state_required = True

        # Send the new blocks
        for block in new_blocks:
            position_to_send = cast(LivePosition, block.positions[0])

            message_text = MessageTemplate.format_signal(position_to_send, self._symbol)
            message_id = await self._telegram_client.send_message(message_text)

            assert isinstance(message_id, int)
            # The +1 is because Cornix re-sends the message with an inline keyboard attached.
            position_to_send.telegram_message_id = message_id + 1
            position_to_send.signal_sent = True
            _save_state_required = True

        self._current_blocks = updated_blocks_set

        if _save_state_required:
            self._save_state()
