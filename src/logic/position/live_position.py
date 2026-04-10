"""
A forward-test ready version of Position object with Telegram message ID and signal_Sent properties defined.
"""

from typing import Optional

from ..blocks.block import Block
from .position import Position


class LivePosition(Position):
    def __init__(self, base_block: Block):
        super().__init__(base_block)

        self.telegram_message_id: Optional[int] = None
        self.signal_sent = False
        self.signal_canceled = False
