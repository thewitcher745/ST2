"""
This folder contains modules that would simulate live forward test data from a cached and loaded
pandas dataframe.
"""

from .tick_provider import SimulatedTickProvider


__all__ = ["SimulatedTickProvider"]
