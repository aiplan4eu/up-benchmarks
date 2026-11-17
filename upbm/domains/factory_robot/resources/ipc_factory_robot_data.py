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

"""The 20 shipped IPC-2026 factory-robot instances, as data.

Every number here is simply what the shipped files say; none of it is
derived. Keys of IPC_INSTANCES are the number in the file name: pfile1 -> 1
... pfile20 -> 20. pfile1 and pfile2 are identical in the dataset, so their
rows are too.

What every instance shares is not stored: the robots are r0 ... rN-1; the
stations are charging, cooling, assembly0, assembly1 ..., connected both
ways between every pair; the charger is on charging and the calibrator on
cooling; every station no robot starts on is free; every robot starts
calibrated with workload, temperature and production at 0; and
cooling-power is 0 on every station but cooling. The goal asks every robot
for a workload target, and r0 alone for a temperature bound.

Each entry of IPC_INSTANCES holds:

- ``file``              the shipped file the entry was read from.
- ``n_stations``        how many stations the factory has.
- ``cooling_power``     the cooling-power of the cooling station.
- ``goal_temperature``  the X of the goal (<= (temperature r0) X).
- ``robots``            one row per robot, r0 first: the station it starts
  on, its workload target (the X of (>= (workload ri) X)), then its values
  of ROBOT_FLUENTS in that order.
"""

from typing import Any, Dict

# The per-robot functions at the end of each robot's row, in that order.
ROBOT_FLUENTS = (
    "energy",
    "capacity",
    "work-cost",
    "max-temp",
    "efficiency",
)

# Annotated, or mypy infers the heterogeneous rows as dict[str, object].
IPC_INSTANCES: Dict[int, Dict[str, Any]] = {
    1: {
        "file": "pfile1",
        "n_stations": 5,
        "cooling_power": 6,
        "goal_temperature": 20,
        "robots": [
            ("assembly1", 38, 79, 80, 12, 21, 4),
            ("cooling", 39, 80, 80, 10, 21, 2),
        ],
    },
    2: {
        "file": "pfile2",
        "n_stations": 5,
        "cooling_power": 6,
        "goal_temperature": 20,
        "robots": [
            ("assembly1", 38, 79, 80, 12, 21, 4),
            ("cooling", 39, 80, 80, 10, 21, 2),
        ],
    },
    3: {
        "file": "pfile3",
        "n_stations": 6,
        "cooling_power": 6,
        "goal_temperature": 20,
        "robots": [
            ("cooling", 38, 73, 80, 10, 25, 4),
            ("assembly0", 42, 64, 80, 10, 20, 4),
            ("assembly3", 39, 101, 120, 10, 25, 2),
        ],
    },
    4: {
        "file": "pfile4",
        "n_stations": 6,
        "cooling_power": 6,
        "goal_temperature": 20,
        "robots": [
            ("cooling", 43, 73, 80, 10, 25, 4),
            ("assembly0", 47, 64, 80, 10, 20, 4),
            ("assembly3", 44, 101, 120, 10, 25, 2),
        ],
    },
    5: {
        "file": "pfile5",
        "n_stations": 7,
        "cooling_power": 6,
        "goal_temperature": 25,
        "robots": [
            ("assembly0", 46, 62, 80, 10, 29, 2),
            ("assembly3", 45, 72, 80, 10, 28, 2),
            ("assembly4", 45, 120, 120, 8, 25, 2),
            ("assembly1", 44, 95, 100, 8, 25, 4),
        ],
    },
    6: {
        "file": "pfile6",
        "n_stations": 7,
        "cooling_power": 6,
        "goal_temperature": 25,
        "robots": [
            ("assembly0", 51, 62, 80, 10, 29, 2),
            ("assembly3", 50, 72, 80, 10, 28, 2),
            ("assembly4", 50, 120, 120, 8, 25, 2),
            ("assembly1", 49, 95, 100, 8, 25, 4),
        ],
    },
    7: {
        "file": "pfile7",
        "n_stations": 8,
        "cooling_power": 6,
        "goal_temperature": 25,
        "robots": [
            ("assembly5", 50, 67, 80, 10, 25, 4),
            ("assembly3", 48, 70, 80, 8, 25, 2),
            ("charging", 48, 112, 120, 8, 26, 4),
            ("assembly0", 51, 96, 100, 15, 26, 2),
            ("assembly2", 48, 94, 100, 8, 29, 4),
        ],
    },
    8: {
        "file": "pfile8",
        "n_stations": 8,
        "cooling_power": 6,
        "goal_temperature": 30,
        "robots": [
            ("assembly5", 60, 67, 80, 10, 30, 4),
            ("assembly3", 58, 70, 80, 8, 30, 2),
            ("charging", 58, 112, 120, 8, 31, 4),
            ("assembly0", 61, 96, 100, 15, 31, 2),
            ("assembly2", 58, 94, 100, 8, 34, 4),
        ],
    },
    9: {
        "file": "pfile9",
        "n_stations": 9,
        "cooling_power": 4,
        "goal_temperature": 30,
        "robots": [
            ("assembly3", 58, 76, 80, 8, 31, 2),
            ("assembly0", 60, 74, 80, 8, 31, 4),
            ("assembly6", 60, 110, 120, 15, 34, 4),
            ("assembly1", 62, 97, 100, 8, 34, 4),
            ("cooling", 60, 98, 100, 8, 30, 4),
            ("charging", 58, 88, 100, 8, 34, 3),
        ],
    },
    10: {
        "file": "pfile10",
        "n_stations": 9,
        "cooling_power": 4,
        "goal_temperature": 30,
        "robots": [
            ("assembly3", 68, 76, 80, 8, 31, 2),
            ("assembly0", 70, 74, 80, 8, 31, 4),
            ("assembly6", 70, 110, 120, 15, 34, 4),
            ("assembly1", 72, 97, 100, 8, 34, 4),
            ("cooling", 70, 98, 100, 8, 30, 4),
            ("charging", 68, 88, 100, 8, 34, 3),
        ],
    },
    11: {
        "file": "pfile11",
        "n_stations": 10,
        "cooling_power": 4,
        "goal_temperature": 35,
        "robots": [
            ("assembly2", 71, 68, 80, 8, 39, 4),
            ("assembly1", 72, 77, 80, 15, 39, 4),
            ("charging", 68, 109, 120, 8, 35, 3),
            ("assembly6", 71, 89, 100, 8, 39, 2),
            ("assembly5", 68, 81, 100, 8, 36, 3),
            ("cooling", 72, 92, 100, 10, 40, 4),
            ("assembly7", 70, 79, 80, 10, 40, 3),
        ],
    },
    12: {
        "file": "pfile12",
        "n_stations": 10,
        "cooling_power": 4,
        "goal_temperature": 35,
        "robots": [
            ("assembly2", 81, 68, 80, 8, 39, 4),
            ("assembly1", 82, 77, 80, 15, 39, 4),
            ("charging", 78, 109, 120, 8, 35, 3),
            ("assembly6", 81, 89, 100, 8, 39, 2),
            ("assembly5", 78, 81, 100, 8, 36, 3),
            ("cooling", 82, 92, 100, 10, 40, 4),
            ("assembly7", 80, 79, 80, 10, 40, 3),
        ],
    },
    13: {
        "file": "pfile13",
        "n_stations": 11,
        "cooling_power": 4,
        "goal_temperature": 35,
        "robots": [
            ("assembly1", 80, 63, 80, 15, 40, 3),
            ("assembly6", 82, 77, 80, 8, 40, 2),
            ("assembly5", 79, 108, 120, 8, 40, 2),
            ("assembly2", 78, 98, 100, 8, 39, 4),
            ("assembly8", 78, 83, 100, 10, 38, 3),
            ("assembly0", 79, 91, 100, 10, 36, 3),
            ("charging", 80, 60, 80, 8, 38, 3),
            ("assembly4", 78, 61, 80, 10, 39, 2),
        ],
    },
    14: {
        "file": "pfile14",
        "n_stations": 11,
        "cooling_power": 4,
        "goal_temperature": 35,
        "robots": [
            ("assembly1", 90, 63, 80, 15, 40, 3),
            ("assembly6", 92, 77, 80, 8, 40, 2),
            ("assembly5", 89, 108, 120, 8, 40, 2),
            ("assembly2", 88, 98, 100, 8, 39, 4),
            ("assembly8", 88, 83, 100, 10, 38, 3),
            ("assembly0", 89, 91, 100, 10, 36, 3),
            ("charging", 90, 60, 80, 8, 38, 3),
            ("assembly4", 88, 61, 80, 10, 39, 2),
        ],
    },
    15: {
        "file": "pfile15",
        "n_stations": 12,
        "cooling_power": 6,
        "goal_temperature": 40,
        "robots": [
            ("assembly3", 91, 62, 80, 8, 43, 2),
            ("assembly7", 90, 74, 80, 8, 44, 2),
            ("assembly4", 91, 118, 120, 8, 42, 3),
            ("assembly0", 90, 99, 100, 10, 40, 2),
            ("assembly9", 89, 93, 100, 10, 41, 2),
            ("assembly8", 90, 91, 100, 8, 45, 3),
            ("assembly1", 90, 78, 80, 10, 43, 2),
            ("cooling", 89, 73, 80, 15, 42, 3),
            ("assembly6", 90, 147, 150, 10, 42, 3),
        ],
    },
    16: {
        "file": "pfile16",
        "n_stations": 12,
        "cooling_power": 6,
        "goal_temperature": 40,
        "robots": [
            ("assembly3", 101, 62, 80, 8, 43, 2),
            ("assembly7", 100, 74, 80, 8, 44, 2),
            ("assembly4", 101, 118, 120, 8, 42, 3),
            ("assembly0", 100, 99, 100, 10, 40, 2),
            ("assembly9", 99, 93, 100, 10, 41, 2),
            ("assembly8", 100, 91, 100, 8, 45, 3),
            ("assembly1", 100, 78, 80, 10, 43, 2),
            ("cooling", 99, 73, 80, 15, 42, 3),
            ("assembly6", 100, 147, 150, 10, 42, 3),
        ],
    },
    17: {
        "file": "pfile17",
        "n_stations": 13,
        "cooling_power": 6,
        "goal_temperature": 40,
        "robots": [
            ("assembly5", 100, 71, 80, 8, 40, 2),
            ("assembly1", 100, 78, 80, 8, 41, 3),
            ("assembly0", 99, 113, 120, 10, 45, 2),
            ("assembly9", 100, 97, 100, 10, 43, 3),
            ("charging", 98, 88, 100, 8, 42, 3),
            ("assembly8", 102, 92, 100, 10, 42, 4),
            ("assembly7", 99, 66, 80, 15, 41, 3),
            ("assembly3", 102, 60, 80, 10, 41, 2),
            ("assembly2", 99, 139, 150, 15, 42, 4),
            ("assembly6", 99, 75, 80, 12, 40, 3),
        ],
    },
    18: {
        "file": "pfile18",
        "n_stations": 13,
        "cooling_power": 6,
        "goal_temperature": 40,
        "robots": [
            ("assembly5", 120, 71, 80, 8, 40, 2),
            ("assembly1", 120, 78, 80, 8, 41, 3),
            ("assembly0", 119, 113, 120, 10, 45, 2),
            ("assembly9", 120, 97, 100, 10, 43, 3),
            ("charging", 118, 88, 100, 8, 42, 3),
            ("assembly8", 122, 92, 100, 10, 42, 4),
            ("assembly7", 119, 66, 80, 15, 41, 3),
            ("assembly3", 122, 60, 80, 10, 41, 2),
            ("assembly2", 119, 139, 150, 15, 42, 4),
            ("assembly6", 119, 75, 80, 12, 40, 3),
        ],
    },
    19: {
        "file": "pfile19",
        "n_stations": 14,
        "cooling_power": 6,
        "goal_temperature": 50,
        "robots": [
            ("assembly6", 122, 60, 80, 10, 52, 2),
            ("assembly0", 119, 69, 80, 10, 51, 4),
            ("assembly3", 119, 115, 120, 8, 51, 3),
            ("assembly7", 121, 89, 100, 10, 52, 4),
            ("assembly8", 121, 89, 100, 15, 50, 2),
            ("assembly5", 120, 94, 100, 10, 50, 3),
            ("assembly4", 122, 72, 80, 15, 53, 2),
            ("assembly10", 119, 60, 80, 12, 50, 4),
            ("assembly2", 120, 148, 150, 8, 52, 3),
            ("assembly11", 118, 61, 80, 10, 52, 4),
            ("charging", 119, 60, 80, 15, 54, 4),
            ("cooling", 118, 75, 80, 12, 52, 3),
        ],
    },
    20: {
        "file": "pfile20",
        "n_stations": 14,
        "cooling_power": 6,
        "goal_temperature": 50,
        "robots": [
            ("assembly6", 132, 60, 80, 10, 52, 2),
            ("assembly0", 129, 69, 80, 10, 51, 4),
            ("assembly3", 129, 115, 120, 8, 51, 3),
            ("assembly7", 131, 89, 100, 10, 52, 4),
            ("assembly8", 131, 89, 100, 15, 50, 2),
            ("assembly5", 130, 94, 100, 10, 50, 3),
            ("assembly4", 132, 72, 80, 15, 53, 2),
            ("assembly10", 129, 60, 80, 12, 50, 4),
            ("assembly2", 130, 148, 150, 8, 52, 3),
            ("assembly11", 128, 61, 80, 10, 52, 4),
            ("charging", 129, 60, 80, 15, 54, 4),
            ("cooling", 128, 75, 80, 12, 52, 3),
        ],
    },
}
