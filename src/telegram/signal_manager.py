from pathlib import Path
from typing import cast
import pickle
import logging
from httpx import HTTPStatusError

from src.arg_parser import RuntimeArgParser
from src.logic import LivePosition
from src.logic.blocks.block import Block
from src.telegram import TelegramClient
from src.config import Config
from .message_template import MessageTemplate

logger = logging.getLogger("[SignalManager]")
config = Config()

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class SignalManager:
    def __init__(self, symbol: str, telegram_client: TelegramClient):
        self._telegram_client = telegram_client
        self._current_active_blocks: set[Block] = set()
        self._sent_blocks: set[Block] = set()
        self._initial_run: bool = (
            True  # Set to true since the first set of signals haven't been sent yet.
        )
        self._symbol = symbol
        self._state_filepath = BASE_DIR / "data" / "state" / f"{symbol}.pickle"

        self._load_state()

    def _save_state(self):
        """Save the current state to disk."""
        state = {
            "_current_active_blocks": self._current_active_blocks,
            "initial_run": self._initial_run,
            "sent_blocks": self._sent_blocks,
        }
        with open(self._state_filepath, "wb") as f:
            pickle.dump(state, f)

    def _load_state(self):
        """Load state from disk if it exists."""
        try:
            with open(self._state_filepath, "rb") as f:
                state = pickle.load(f)
                self._current_active_blocks = state["_current_active_blocks"]
                self._initial_run = state["initial_run"]
                self._sent_blocks = state["sent_blocks"]
            logger.info(f"Loaded state for {self._symbol}")
        except FileNotFoundError:
            logger.info(f"No saved state found for {self._symbol}, starting fresh")

    async def process_signals(self, updated_blocks: list[Block], current_price: float):
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
            old_blocks_set = self._current_active_blocks

        # Blocks that were there in the previous frame but not in the new update's active blocks
        outdated_blocks = old_blocks_set - updated_blocks_set

        # Blocks that now exist but haven't been sent yet
        pending_blocks = updated_blocks_set - self._sent_blocks

        # Only save the state if anything changes.
        _save_state_required = False

        # Cancel the outdated blocks
        for block in outdated_blocks:
            if block in self._sent_blocks:
                position_to_cancel = cast(LivePosition, block.positions[0])
                if not position_to_cancel.entered:
                    assert isinstance(position_to_cancel, LivePosition)

                    message_text = "Cancel"
                    reply_id = position_to_cancel.telegram_message_id

                    # Sometimes, if the message has been deleted or is otherwise unreachable, Telegram returns
                    # an error. This shouldn't happen, but it's safer to handle the error here as well.
                    try:
                        # In a dry run nothing is sent to the channels.
                        if not RuntimeArgParser().args.dry:
                            await self._telegram_client.send_message(
                                message_text, reply_id=reply_id
                            )
                    except HTTPStatusError as e:
                        if (
                            e.response.status_code == 400
                            and "message to be replied not found" in e.response.text
                        ):
                            logger.warning(
                                f"Cannot cancel position {position_to_cancel.id} - original message deleted"
                            )
                            continue
                        else:
                            raise

                    logger.info(
                        f"Canceled position with ID {position_to_cancel.id} for symbol {self._symbol}, reply_id {reply_id}"
                    )

                    position_to_cancel.signal_canceled = True
                    _save_state_required = True

        # Send the new and pending blocks
        for block in pending_blocks:
            position_to_send = cast(LivePosition, block.positions[0])
            if block in outdated_blocks:
                continue

            if not self._is_signal_sendable(position_to_send, current_price):
                continue

            message_text = MessageTemplate.format_signal(position_to_send, self._symbol)

            message_id = 0
            # In a dry run nothing is sent to the channels.
            if not RuntimeArgParser().args.dry:
                message_id = await self._telegram_client.send_message(message_text)

            logger.info(
                f"Sent position with ID {position_to_send.id} for symbol {self._symbol}, message_id {message_id}"
            )

            assert isinstance(message_id, int)
            # The +1 is because Cornix re-sends the message with an inline keyboard attached.
            position_to_send.telegram_message_id = message_id + 1
            position_to_send.signal_sent = True
            _save_state_required = True

            self._sent_blocks.add(block)

        self._current_active_blocks = updated_blocks_set

        if _save_state_required:
            self._save_state()

    def _is_signal_sendable(self, position: LivePosition, current_price: float):
        # Is the price close enough to the signal to post?
        if bool(config.get("signal_proximity_check")):
            proximity_check_percent = float(
                config.get("signal_proximity_check_percent")
            )

            if position.type == "long":
                if current_price > position.entry * (1 + proximity_check_percent / 100):
                    return False
                return True
            else:
                if current_price < position.entry * (1 - proximity_check_percent / 100):
                    return False
                return True

        # Is the price valid in relation to the stoploss?
        if position.type == "long":
            return current_price > position.stoplosses[0]
        else:
            return current_price < position.stoplosses[0]
