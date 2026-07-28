from pathlib import Path
import pickle
import logging
from httpx import HTTPStatusError
from datetime import datetime, timedelta

from src.logic import Position
from src.telegram import TelegramClient
from src.config import Config
from .message_template import MessageTemplate

logger = logging.getLogger("[SignalManager]")
config = Config()

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class SignalManager:
    def __init__(self, symbol: str, telegram_client: TelegramClient):
        self._telegram_client = telegram_client
        self._current_active_positions: set[Position] = set()
        # A dict of sent positions' ID's and their message ID's, used for cancelations
        self._sent_positions_message_ids: dict[str, int] = {}
        # A list of omitted positions, which are positions that we decide will not be posted ever.
        self._omitted_positions: set[Position] = set()
        self._initial_run: bool = (
            True  # Set to true since the first set of signals haven't been sent yet.
        )
        self._symbol = symbol
        self._state_filepath = (
            BASE_DIR / "data" / "state" / config.run_id / f"{symbol}.pickle"
        )

        # Bot launch time
        self._signal_manager_launch_time = datetime.now()

        # Timer for debug logging
        self._last_debug_log_time: datetime | None = None
        self._debug_log_interval = timedelta(minutes=30)

        self._load_state()

    def _should_log_debug(self) -> bool:
        """Check if enough time has passed since last debug log."""
        now = datetime.now()
        if self._last_debug_log_time is None:
            self._last_debug_log_time = now
            return True

        if now - self._last_debug_log_time >= self._debug_log_interval:
            self._last_debug_log_time = now
            return True

        return False

    def _save_state(self):
        """Save the current state to disk."""
        state = {
            "_current_active_positions": self._current_active_positions,
            "initial_run": self._initial_run,
            "sent_positions_message_ids": self._sent_positions_message_ids,
        }
        with open(self._state_filepath, "wb") as f:
            pickle.dump(state, f)

    def _load_state(self):
        """Load state from disk if it exists."""
        try:
            with open(self._state_filepath, "rb") as f:
                state = pickle.load(f)
                self._current_active_positions = state["_current_active_positions"]
                self._initial_run = state["initial_run"]
                self._sent_positions_message_ids = state["sent_positions_message_ids"]
            logger.info(f"Loaded state for {self._symbol}")
        except FileNotFoundError:
            logger.info(f"No saved state found for {self._symbol}, starting fresh")

    async def process_signals(
        self, updated_positions: list[Position], current_price: float
    ):
        """
        Compares the current position ids to the old ones. If there's a new position which has not been entered,
        sends its signal to the channel.

        Args:
            updated_positions: List of Position objects found in the most recent update (recalc)
        """
        updated_positions_set = set(updated_positions)

        # If we're sending the first set of signals,
        if self._initial_run:
            old_positions_set = set()
            self._initial_run = False
        else:
            old_positions_set = self._current_active_positions

        # Positions that were there in the previous frame but not in the new update's active positions
        outdated_positions = old_positions_set - updated_positions_set

        # Positions that now exist but haven't been sent yet
        pending_positions = []
        for position in updated_positions_set:
            if position.id in self._sent_positions_message_ids.keys():
                continue

            if not self._may_become_sendable(position):
                if position not in self._omitted_positions:
                    logger.debug(
                        f"[{self._symbol}] Position with ID {position.id} will never be posted since it has been entered before."
                    )
                    self._omitted_positions.add(position)
                continue

            pending_positions.append(position)

        # Debug logging with timer
        if self._should_log_debug():
            logger.debug(
                f"[{self._symbol}] Outdated positions: {[b.id for b in outdated_positions]}"
            )
            logger.debug(
                f"[{self._symbol}] Pending positions: {[b.id for b in pending_positions]}"
            )
            logger.debug(
                f"[{self._symbol}] Already sent: {list(self._sent_positions_message_ids.keys())}"
            )

        # Only save the state if anything changes.
        _save_state_required = False

        # Cancel the outdated positions
        for position in outdated_positions:
            if position.id in self._sent_positions_message_ids.keys():
                if position.entered:
                    logger.debug(
                        f"[{self._symbol}] Position {position.id} is entered, skipping cancellation"
                    )
                    continue

                if position.base_block.end_index is None:
                    continue

                if self._is_signal_cancelable(position):
                    message_text = "Cancel"
                    reply_id = self._sent_positions_message_ids[position.id]

                    # Sometimes, if the message has been deleted or is otherwise unreachable, Telegram returns
                    # an error. This shouldn't happen, but it's safer to handle the error here as well.
                    logger.info(
                        f"[{self._symbol}] Canceling position with ID {position.id} for symbol {self._symbol}, reply_id {reply_id}"
                    )
                    logger.info(
                        f"Position with ID {position.id} entered status: Entered? {position.entered} Entry time: {position.entry_time}"
                    )
                    try:
                        # In a dry run nothing is sent to the channels.
                        if not config.dry:
                            await self._telegram_client.send_message(
                                message_text, reply_id=reply_id
                            )
                    except HTTPStatusError as e:
                        if (
                            e.response.status_code == 400
                            and "message to be replied not found" in e.response.text
                        ):
                            logger.warning(
                                f"[{self._symbol}] Cannot cancel position {position.id} - original message deleted"
                            )

                            del self._sent_positions_message_ids[position.id]
                            _save_state_required = True

                            continue
                        else:
                            raise

                    del self._sent_positions_message_ids[position.id]

                    _save_state_required = True

        # Send the new and pending positions
        for position in pending_positions:
            if position in outdated_positions:
                continue

            if not self._is_signal_sendable(position, current_price):
                continue

            message_text = MessageTemplate.format_signal(position, self._symbol)

            message_id = 0

            if not config.dry:
                message_id = await self._telegram_client.send_message(message_text)

            # In a dry run nothing is sent to the channels.
            logger.info(
                f"[{self._symbol}] Sending position with ID {position.id}, message_id {message_id}"
            )

            assert isinstance(message_id, int)
            # The +1 is because Cornix re-sends the message with an inline keyboard attached.
            self._sent_positions_message_ids[position.id] = message_id + 1
            _save_state_required = True

        self._current_active_positions = updated_positions_set

        if _save_state_required:
            self._save_state()

    def _may_become_sendable(self, position: Position) -> bool:
        """
        Returns True if the signal might still be sendable in the future.
        """
        # Don't keep the signal if it has been entered before the bot's launch time.
        if position.entered:
            if (
                position.entry_time is not None
                and position.entry_time < self._signal_manager_launch_time
            ):
                return False

        return True

    def _is_signal_sendable(self, position: Position, current_price: float):
        # Is the price close enough to the signal to post?
        if config.signal_proximity_check:
            proximity_check_percent = config.signal_proximity_check_percent

            if position.type == "long":
                if current_price > position.entry * (1 + proximity_check_percent / 100):
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

        return True

    def _is_signal_cancelable(self, position: Position):
        # If the position has been entered, don't cancel it.
        if position.entered:
            return False

        return True
