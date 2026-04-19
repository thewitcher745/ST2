import argparse
from typing import Any, Optional
from dotenv import dotenv_values

from .config_schema import CONFIG_SCHEMA


def schema_typecast(val: Any, var_name: str) -> Any:
    """
    Type-casts a variable with a given name and returns it as the correct type.
    Types are defined in config_schema.py.
    """
    typecast_function = CONFIG_SCHEMA.get(var_name, None)

    if var_name not in CONFIG_SCHEMA or typecast_function is None:
        raise AttributeError(
            f"Variable with name <{var_name}> not found in config schema!"
        )

    # Boolean variables need special treatment
    if type(val) is bool:
        return val

    if typecast_function is bool:
        if val is not None:
            return val.lower() in ("true", "1", "yes")
        return False

    return typecast_function(val)


class Config:
    _instance = None
    _initialized = False

    # Type declarations
    lag: int
    fib_factor: float
    timeframe: str
    target_coeff: float
    stoploss_coeff: float
    target_setup_function: str
    stoploss_setup_function: str
    usdt_per_trade: float
    leverage: float
    leverage_type: str
    startup_n_days: int
    calc_interval: float
    binance_ws_endpoint: str
    telegram_api_endpoint: str
    live_sim_tick_interval: float
    binance_cache_retry_interval: float
    binance_cache_max_retries: int
    binance_cache_resync_buffer: int
    telegram_api_max_retries: int
    telegram_api_base_retry_interval: float
    telegram_api_send_message_delay: float
    ws_error_retry_interval: float
    ws_error_max_retries: int
    validation: bool
    signal_proximity_check: bool
    signal_proximity_check_percent: int
    chart_data_write_interval: float
    proxy_server: Optional[str] = None
    dev: Optional[bool] = False

    # Credentials
    TG_BOT_AUTH_TOKEN: str
    TG_DEV_CHANNEL_ID: str
    TG_PROD_CHANNEL_ID: str

    # Runtime args
    clear_logs: bool
    clear_state: bool
    clear_klines: bool
    dry: bool
    clean: bool
    symbols_filename: str
    direction: str

    def _get_args(self):
        argument_parser = argparse.ArgumentParser("ST2 Runtime args")

        argument_parser.add_argument(
            "--clear_logs", action="store_true"
        )  # Clears the logs
        argument_parser.add_argument(
            "--clear_state", action="store_true"
        )  # Clears the state files
        argument_parser.add_argument(
            "--clear_klines",
            action="store_true",
        )  # Clears the KLines files
        argument_parser.add_argument(
            "--dry",
            action="store_true",
            help="Doesn't post anything to any Telegram channel, for debugging purposes.",
        )  # Only logs positions to console, not Telegram posting
        argument_parser.add_argument(
            "-c",
            "--clean",
            action="store_true",
            help="Clears all caches and logs before running.",
        )  # Cleans everything
        argument_parser.add_argument(
            "-s",
            "--symbols_filename",
            default="symbols.csv",
            help="Name of the CSV file containing the symbols in data/symbol_lists",
        )  # Name of the .CSV file containing the symbols for the forward test
        argument_parser.add_argument(
            "-d",
            "--direction",
            choices=["long", "short", "both"],
            default=None,
            help="Limit the positions to one direction only.",
        )  # Name of the .CSV file containing the symbols for the forward test

        return argument_parser.parse_args()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)

        return cls._instance

    def __init__(
        self,
        config_env_path: str = ".env.config",
        misc_env_path: str = ".env.misc",
        misc_local_env_path: str = ".env.misc.local",
        secret_env_path: str = ".env.secret",
    ):
        if Config._initialized:
            return

        config_values = dotenv_values(config_env_path)
        misc_values = dotenv_values(misc_env_path)
        misc_local_values = dotenv_values(misc_local_env_path)
        secret_values = dotenv_values(secret_env_path)

        args = self._get_args()

        for key, value in config_values.items():
            self.__setattr__(key, schema_typecast(value, key))

        for key, value in misc_values.items():
            self.__setattr__(key, schema_typecast(value, key))

        for key, value in secret_values.items():
            self.__setattr__(key, schema_typecast(value, key))

        for key, value in misc_local_values.items():
            self.__setattr__(key, schema_typecast(value, key))

        for key, value in args.__dict__.items():
            self.__setattr__(key, schema_typecast(value, key))

        Config._initialized = True

    def __repr__(self):
        output = "Current config:\n"
        for key, value in self.__dict__.items():
            output += f"\t{key}: {value}\n"

        return output
