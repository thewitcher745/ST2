"""
Random, small utilities and constants.
"""

# This dict defines which direction each level is. The correct direction of the level
# is then determined by subtracting them. If the sign of deducing the first event from the
# second is negative, that means the order should be reversed.
change_directions_dict = {
    "long": {"target": 1, "entry": 0, "stop": -1},
    "short": {"target": -1, "entry": 0, "stop": 1},
}
