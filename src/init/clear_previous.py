"""
Module for clearing the logs and state from previous runs, if the flag for it is set.
"""

import os
import shutil

from src.arg_parser import RuntimeArgParser


def _clear_dir(dir: str) -> bool:
    """Clears a directory except .gitkeep, returns True if any files were removed."""
    if not os.path.exists(dir):
        return False

    removed = False

    for entry in os.listdir(dir):
        path = os.path.join(dir, entry)

        if entry == ".gitkeep":
            continue

        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path)
            removed = True
        elif os.path.isdir(path):
            shutil.rmtree(path)
            removed = True

    return removed


def _clear_state():
    state_dir = "data/state"

    if _clear_dir(state_dir):
        print("State directory cleared.")
    else:
        print("State directory not found or already empty.")


def _clear_logs():
    state_dir = "logs"

    if _clear_dir(state_dir):
        print("Logs directory cleared.")
    else:
        print("Logs directory not found or already empty.")


def _clear_klines():
    state_dir = "data/klines"

    if _clear_dir(state_dir):
        print("KLines directory cleared.")
    else:
        print("KLines directory not found or already empty.")


def clear_previous():
    args = RuntimeArgParser().args
    if args.clear_logs or args.clean:
        _clear_logs()

    if args.clear_state or args.clean:
        _clear_state()

    if args.clear_klines or args.clean:
        _clear_klines()
