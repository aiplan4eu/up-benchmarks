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

"""The twenty shipped IPC-2026 line-exchange-snp instances, written down as data.

The "ipc" variant rebuilds these instead of taking the loads as parameters, so
its only instance parameter is the index below. The order is the one the dataset
lists the files in, so index 0 is ``3_10_50_10``.

Why a table at all: the shipped file names encode
``<n_robots>_<mean_q>_<imbalance%>_<D>``, but only ``n_robots`` and ``D`` are
recoverable parameters. The loads were drawn at random with no seed recorded,
and ``imbalance`` does not determine them - ``3_10_90_50`` holds ``[10, 9, 11]``
and ``3_15_90_10`` holds ``[35, 6, 4]``, both at imbalance 90. So the loads are
row data, not a rule, and this table is what "reproducing the set" means here.

Each entry holds everything needed to rebuild that instance:

- ``name``            the shipped file name, which is also the instance name the
                      yml uses;
- ``n_robots``        how many robots are on the line;
- ``segment_length``  the ``D`` fluent. Robot *i* owns ``[D*i, D*(i+1)]`` and
                      starts, and must end, in the middle of it at ``D/2 + i*D``;
- ``loads``           the starting load of each robot, in order. Their sum always
                      divides evenly by ``n_robots``, which is what makes the
                      levelled-out goal reachable;
- ``mean_q``          the file name's mean load, kept only as provenance:
                      ``sum(loads) == n_robots * mean_q`` in all twenty;
- ``imbalance``       the file name's imbalance percentage, likewise provenance.
                      The "unbounded_random" variant takes it as a real dial.

``mean_q`` and ``imbalance`` are never read when building an instance. They are
here so the table explains where its own numbers came from.
"""

from typing import Any, Dict, List

IPC_INSTANCES: Dict[int, Dict[str, Any]] = {
    0: {
        "name": "3_10_50_10",
        "n_robots": 3,
        "segment_length": 10,
        "loads": [12, 12, 6],
        "mean_q": 10,
        "imbalance": 50,
    },
    1: {
        "name": "3_10_90_50",
        "n_robots": 3,
        "segment_length": 50,
        "loads": [10, 9, 11],
        "mean_q": 10,
        "imbalance": 90,
    },
    2: {
        "name": "3_15_25_100",
        "n_robots": 3,
        "segment_length": 100,
        "loads": [14, 19, 12],
        "mean_q": 15,
        "imbalance": 25,
    },
    3: {
        "name": "3_15_90_10",
        "n_robots": 3,
        "segment_length": 10,
        "loads": [35, 6, 4],
        "mean_q": 15,
        "imbalance": 90,
    },
    4: {
        "name": "3_5_50_50",
        "n_robots": 3,
        "segment_length": 50,
        "loads": [3, 6, 6],
        "mean_q": 5,
        "imbalance": 50,
    },
    5: {
        "name": "3_5_90_100",
        "n_robots": 3,
        "segment_length": 100,
        "loads": [3, 3, 9],
        "mean_q": 5,
        "imbalance": 90,
    },
    6: {
        "name": "4_10_25_10",
        "n_robots": 4,
        "segment_length": 10,
        "loads": [11, 12, 8, 9],
        "mean_q": 10,
        "imbalance": 25,
    },
    7: {
        "name": "4_10_50_50",
        "n_robots": 4,
        "segment_length": 50,
        "loads": [13, 9, 5, 13],
        "mean_q": 10,
        "imbalance": 50,
    },
    8: {
        "name": "4_10_90_100",
        "n_robots": 4,
        "segment_length": 100,
        "loads": [2, 18, 3, 17],
        "mean_q": 10,
        "imbalance": 90,
    },
    9: {
        "name": "4_15_50_10",
        "n_robots": 4,
        "segment_length": 10,
        "loads": [13, 12, 17, 18],
        "mean_q": 15,
        "imbalance": 50,
    },
    10: {
        "name": "4_15_90_50",
        "n_robots": 4,
        "segment_length": 50,
        "loads": [24, 12, 18, 6],
        "mean_q": 15,
        "imbalance": 90,
    },
    11: {
        "name": "4_5_25_50",
        "n_robots": 4,
        "segment_length": 50,
        "loads": [6, 4, 4, 6],
        "mean_q": 5,
        "imbalance": 25,
    },
    12: {
        "name": "4_5_50_100",
        "n_robots": 4,
        "segment_length": 100,
        "loads": [4, 4, 8, 4],
        "mean_q": 5,
        "imbalance": 50,
    },
    13: {
        "name": "5_10_25_50",
        "n_robots": 5,
        "segment_length": 50,
        "loads": [7, 10, 11, 12, 10],
        "mean_q": 10,
        "imbalance": 25,
    },
    14: {
        "name": "5_10_50_100",
        "n_robots": 5,
        "segment_length": 100,
        "loads": [9, 9, 13, 9, 10],
        "mean_q": 10,
        "imbalance": 50,
    },
    15: {
        "name": "5_15_25_10",
        "n_robots": 5,
        "segment_length": 10,
        "loads": [14, 15, 12, 18, 16],
        "mean_q": 15,
        "imbalance": 25,
    },
    16: {
        "name": "5_15_50_50",
        "n_robots": 5,
        "segment_length": 50,
        "loads": [20, 12, 14, 15, 14],
        "mean_q": 15,
        "imbalance": 50,
    },
    17: {
        "name": "5_15_90_100",
        "n_robots": 5,
        "segment_length": 100,
        "loads": [6, 3, 37, 16, 13],
        "mean_q": 15,
        "imbalance": 90,
    },
    18: {
        "name": "5_5_25_100",
        "n_robots": 5,
        "segment_length": 100,
        "loads": [4, 6, 4, 7, 4],
        "mean_q": 5,
        "imbalance": 25,
    },
    19: {
        "name": "5_5_90_10",
        "n_robots": 5,
        "segment_length": 10,
        "loads": [1, 7, 1, 7, 9],
        "mean_q": 5,
        "imbalance": 90,
    },
}


# How many robots the largest shipped instance uses. Only the object universe
# needs this; an instance takes its own count from its row.
MAX_IPC_ROBOTS: int = max(entry["n_robots"] for entry in IPC_INSTANCES.values())
