# Copyright 2026 Unified Planning library and its maintainers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The 20 shipped IPC-2026 petri-net instances, as data.

Keys are the position of the shipped file in name order: prob06-1 -> 1,
prob06-2 -> 2, ... prob10-4 -> 20. The file names carry two numbers, so unlike
other domains they cannot be the key themselves.

The 20 files are only three distinct nets, so the nets are not stored here: the
generator builds them (`NETS` in petri_net.py) and each entry names one. Each
entry holds:

- ``file``         the shipped file the entry was read from.
- ``net``          which of the generator's NETS the instance uses.
- ``goal_style``   which of that net's goal shapes the goal has.
- ``goal_tokens``  the K of the goal's "(= K (value g))".
- ``goal_amount``  the number the goal shape asks for; see GoalStyle.
"""

from typing import Any, Dict

IPC_INSTANCES: Dict[int, Dict[str, Any]] = {
    1: {
        "file": "prob06-1",
        "net": 0,
        "goal_style": 0,
        "goal_tokens": 3,
        "goal_amount": 2,
    },
    2: {
        "file": "prob06-2",
        "net": 0,
        "goal_style": 0,
        "goal_tokens": 2,
        "goal_amount": 2,
    },
    3: {
        "file": "prob06-3",
        "net": 0,
        "goal_style": 0,
        "goal_tokens": 3,
        "goal_amount": 1,
    },
    4: {
        "file": "prob06-4",
        "net": 0,
        "goal_style": 0,
        "goal_tokens": 2,
        "goal_amount": 1,
    },
    5: {
        "file": "prob07-1",
        "net": 1,
        "goal_style": 0,
        "goal_tokens": 3,
        "goal_amount": 2,
    },
    6: {
        "file": "prob07-2",
        "net": 1,
        "goal_style": 0,
        "goal_tokens": 3,
        "goal_amount": 1,
    },
    7: {
        "file": "prob07-3",
        "net": 1,
        "goal_style": 0,
        "goal_tokens": 2,
        "goal_amount": 1,
    },
    8: {
        "file": "prob07-4",
        "net": 1,
        "goal_style": 0,
        "goal_tokens": 1,
        "goal_amount": 1,
    },
    9: {
        "file": "prob08-1",
        "net": 0,
        "goal_style": 1,
        "goal_tokens": 3,
        "goal_amount": 3,
    },
    10: {
        "file": "prob08-2",
        "net": 0,
        "goal_style": 1,
        "goal_tokens": 2,
        "goal_amount": 3,
    },
    11: {
        "file": "prob08-3",
        "net": 0,
        "goal_style": 1,
        "goal_tokens": 3,
        "goal_amount": 1,
    },
    12: {
        "file": "prob08-4",
        "net": 0,
        "goal_style": 1,
        "goal_tokens": 2,
        "goal_amount": 2,
    },
    13: {
        "file": "prob09-1",
        "net": 2,
        "goal_style": 0,
        "goal_tokens": 5,
        "goal_amount": 1,
    },
    14: {
        "file": "prob09-2",
        "net": 2,
        "goal_style": 0,
        "goal_tokens": 4,
        "goal_amount": 1,
    },
    15: {
        "file": "prob09-3",
        "net": 2,
        "goal_style": 0,
        "goal_tokens": 3,
        "goal_amount": 1,
    },
    16: {
        "file": "prob09-4",
        "net": 2,
        "goal_style": 0,
        "goal_tokens": 2,
        "goal_amount": 1,
    },
    17: {
        "file": "prob10-1",
        "net": 2,
        "goal_style": 1,
        "goal_tokens": 5,
        "goal_amount": 0,
    },
    18: {
        "file": "prob10-2",
        "net": 2,
        "goal_style": 1,
        "goal_tokens": 4,
        "goal_amount": 0,
    },
    19: {
        "file": "prob10-3",
        "net": 2,
        "goal_style": 1,
        "goal_tokens": 3,
        "goal_amount": 0,
    },
    20: {
        "file": "prob10-4",
        "net": 2,
        "goal_style": 1,
        "goal_tokens": 2,
        "goal_amount": 0,
    },
}
