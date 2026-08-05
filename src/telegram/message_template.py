from src.logic import Position
from src.config import Config
from .precisions_dict import get_precision

config = Config()


class MessageTemplate:
    @staticmethod
    def _format_price_precision(price: float, symbol: str) -> str:
        precision = get_precision(symbol)

        if precision is None:
            precision = 7

        return f"{price:.{precision}f}"

    @staticmethod
    def _create_trailing_setup_string() -> str:
        if (
            config.stoploss_setup_function == "default"
            or "no_trailing" in config.stoploss_setup_function
        ):
            return ""
        elif "trailing_breakeven_t1" in config.stoploss_setup_function:
            return "\n\nTrailing Configuration:\nStop: Breakeven -\nTrigger: Target (1)"
        else:
            return ""

    @staticmethod
    def format_signal(position: Position, symbol: str) -> str:
        symbol_text = symbol.replace("USDT", "/USDT")

        # Exception for Silver
        if symbol == "XAGUSDT":
            symbol_text = "SILVER(XAG)/USDT"

        leverage = config.leverage
        leverage_type = config.leverage_type
        entry_string = MessageTemplate._format_price_precision(position.entry, symbol)
        targets_string = [
            f"\n{target_id + 1}) {MessageTemplate._format_price_precision(target, symbol)}"
            for target_id, target in enumerate(position.targets)
        ]
        stoploss_string = MessageTemplate._format_price_precision(
            position.stoplosses[0], symbol
        )
        trailing_setup_string = MessageTemplate._create_trailing_setup_string()

        message = f"""⚡⚡ #{symbol_text} ⚡⚡
Exchanges: ByBit USDT, Bitget Futures, BingX Futures, Binance Futures, MEXC Futures
Signal Type: Regular ({position.type})
Leverage: {leverage_type.capitalize()} ({int(leverage)}.0X)

Entry Targets:
1) {entry_string}

Take-Profit Targets:"""

        for target_string in targets_string:
            message += target_string

        message += f"\n\nStop Targets:\n1) {stoploss_string}"

        message += trailing_setup_string

        if config.validation:
            message += f"\n\nID:\n{position.id}"

        return message
