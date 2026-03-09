"""
This function is used to index the functions in target_setup.py as a dict for easy parametrization.
The function names can be passed as strings to the config files and easily changed without touching the code.
"""

from types import FunctionType

from . import target_setup_def


class TargetSetupDir:
    setups: dict[str, FunctionType] = dict()

    for object_name, object_def in target_setup_def.__dict__.items():
        if isinstance(object_def, FunctionType):
            setups[object_name] = object_def
