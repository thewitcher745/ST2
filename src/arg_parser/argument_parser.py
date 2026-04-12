import argparse


class RuntimeArgParser:
    def __init__(self):
        self._argument_parser = argparse.ArgumentParser("ST2 Runtime args")
        self._add_args()

    def _add_args(self):
        self._argument_parser.add_argument(
            "--clear_logs", action="store_true"
        )  # Clears the logs
        self._argument_parser.add_argument(
            "--clear_state", action="store_true"
        )  # Clears the state files
        self._argument_parser.add_argument(
            "--clear_klines", action="store_true"
        )  # Clears the KLines files
        self._argument_parser.add_argument(
            "--dry", action="store_true"
        )  # Only logs positions to console, not Telegram posting
        self._argument_parser.add_argument(
            "--clean", action="store_true"
        )  # Cleans everything

    @property
    def args(self):
        return self._argument_parser.parse_args()
