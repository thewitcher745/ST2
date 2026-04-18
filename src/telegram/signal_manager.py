from pathlib import Path
import pickle
import logging
from httpx import HTTPStatusError

from src.arg_parser import RuntimeArgParser
from src.logic import Position
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
        # A dict of sent blocks' ID's and their message ID's, used for cancelations
        self._sent_blocks_message_ids: dict[str, int] = {}
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
            "sent_blocks_message_ids": self._sent_blocks_message_ids,
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
                self._sent_blocks_message_ids = state["sent_blocks_message_ids"]
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
        pending_blocks = [
            block
            for block in updated_blocks_set
            if block.id not in self._sent_blocks_message_ids.keys()
        ]

        # Only save the state if anything changes.
        _save_state_required = False

        # Cancel the outdated blocks
        for block in outdated_blocks:
            if block.id in self._sent_blocks_message_ids.keys():
                position_to_cancel = block.positions[0]
                if self._is_signal_cancelable(position_to_cancel):
                    assert isinstance(position_to_cancel, Position)

                    message_text = "Cancel"
                    reply_id = self._sent_blocks_message_ids[block.id]

                    # Sometimes, if the message has been deleted or is otherwise unreachable, Telegram returns
                    # an error. This shouldn't happen, but it's safer to handle the error here as well.
                    logger.info(
                        f"Canceling position with ID {position_to_cancel.id} for symbol {self._symbol}, reply_id {reply_id}"
                    )
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

                            del self._sent_blocks_message_ids[block.id]
                            _save_state_required = True

                            continue
                        else:
                            raise

                    del self._sent_blocks_message_ids[block.id]

                    _save_state_required = True

        # Send the new and pending blocks
        for block in pending_blocks:
            position_to_send = block.positions[0]
            if block in outdated_blocks:
                continue

            if not self._is_signal_sendable(position_to_send, current_price):
                continue

            message_text = MessageTemplate.format_signal(position_to_send, self._symbol)

            message_id = 0
            # In a dry run nothing is sent to the channels.
            logger.info(
                f"Sending position with ID {position_to_send.id} for symbol {self._symbol}, message_id {message_id}"
            )
            if not RuntimeArgParser().args.dry:
                message_id = await self._telegram_client.send_message(message_text)

            assert isinstance(message_id, int)
            # The +1 is because Cornix re-sends the message with an inline keyboard attached.
            self._sent_blocks_message_ids[block.id] = message_id + 1
            _save_state_required = True

        self._current_active_blocks = updated_blocks_set

        if _save_state_required:
            self._save_state()

    def _is_signal_sendable(self, position: Position, current_price: float):
        # Is the price close enough to the signal to post?
        if bool(config.get("signal_proximity_check")):
            proximity_check_percent = float(
                config.get("signal_proximity_check_percent")
            )

            if position.type == "long":
                if current_price > position.entry * (
                    1 + proximity_check_percent / 100
                ):
                    return False
            else:
                if current_price < position.entry * (1 - proximity_check_percent / 100):
                    return False

        # Is the price valid in relation to the stoploss?
        if position.type == "long":
            if current_price <= position.stoplosses[0]:
                return False
        else:
            if current_price >= position.stoplosses[0]:
                return False

        # Has the position been entered before? # TODO: Implement bounces. The logic should probably live somewhere around here.
        if position.entered:
            return False

        return True

    def _is_signal_cancelable(self, position: Position):
        # If the position has been entered, don't cancel it.
        if position.entered:
            return False
