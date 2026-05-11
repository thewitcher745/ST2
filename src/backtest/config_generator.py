from itertools import product
from typing import Any
from hashlib import md5

from src.config.config_schema import CONFIG_SCHEMA
from src.config import Config

config = Config()


class ConfigurationGenerator:
    """Generates all possible combinations of the parameters in a dict of ranges."""

    def __init__(self, params_range_dict: dict[str, list]):
        """
        Args:
            params_range_dict: A dict with keys set to the name of each parameter
                and values set to a list of all the values that parameter can take.
        """
        self._params_range_dict = params_range_dict
        self._param_names = list(params_range_dict.keys())
        self._param_values = list(params_range_dict.values())

    def __iter__(self):
        """Yields (run_id, combo_dict) tuples one at a time."""
        for combo_tuple in product(*self._param_values):
            combo_dict = dict(zip(self._param_names, combo_tuple))
            run_id = self._generate_run_id(combo_dict)
            yield (run_id, combo_dict)

    def _generate_run_id(self, combo_dict: dict) -> str:
        """Generates a unique hash of the values in combo_dict."""
        return md5(str(combo_dict).encode("utf-8")).hexdigest()[:12]

    @property
    def count(self) -> int:
        """Returns the total number of combos."""
        result = 1
        for values in self._param_values:
            result *= len(values)

        return result

    @staticmethod
    def override_config_with_combo(combo: dict[str, Any]):
        for key, value in combo.items():
            if key not in CONFIG_SCHEMA:
                raise ValueError(f"Invalid config parameter: {key}")

            config.__setattr__(key, value)
