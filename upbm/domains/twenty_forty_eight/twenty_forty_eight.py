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

from pathlib import Path
from typing import Any, List, Optional, Tuple

from ConfigSpace import (
    ConfigurationSpace,
    Configuration,
    Integer,
    Categorical,
    Constant,
)
from unified_planning.io import PDDLReader
from unified_planning.model import Problem, Object, FNode
from unified_planning.shortcuts import TRUE, Equals

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

# The board is hard-wired 4x4: the domain declares p11..p44 as :constants, so
# its size is fixed by the domain file and is not a parameter.
BOARD_SIZE = 4

# The statuses that name the rows (used when shifting left or right) and the
# columns (used when shifting up or down), in iteration order.
ROW_STATUSES = ("top", "midtop", "midbot", "bot")
COL_STATUSES = ("left", "midleft", "midright", "right")

# The status that marks "every row/column of this sweep has been processed".
DONE_STATUS = "done"

# The four directions, named as the domain names them.
DIRECTIONS = ("L", "R", "U", "D")

# The largest tile a parameter may ask for, as a power of two: 2^13 = 8192.
# The shipped boards only go up to 2048, but 8192 is the largest goal in the
# set, so this leaves room without inventing values the set never shows.
MAX_TILE_EXPONENT = 13

# The goal always collects everything into this position, in all 20 instances.
GOAL_POSITION = "p11"


def position(row: int, col: int) -> str:
    """The domain's name for the cell at 1-based (row, col): p11 .. p44."""
    return f"p{row}{col}"


def tile_parameter(row: int, col: int) -> str:
    """The instance parameter holding the tile at 1-based (row, col)."""
    return f"tile_{row}{col}"


def tile_value(exponent: int) -> int:
    """The tile value an exponent parameter stands for.

    Tiles are given as exponents rather than as values so that a board is a
    legal 2048 board by construction: every value in the game is a power of
    two, and no tile is ever 1, so exponent 0 can mean "empty" with nothing
    to confuse it with.
    """
    return 0 if exponent == 0 else 2**exponent


def board_lines(direction: str) -> List[Tuple[str, List[str]]]:
    """The rows or columns swept by one direction.

    Returns one (status, positions) pair per row or column, where positions
    run from the target edge (index i1) to the far edge (i4). Shifting left
    walks each row starting at the left-hand cell, shifting right walks the
    same rows backwards, and up/down do the same over the columns.
    """
    rows = [
        [position(r, c) for c in range(1, BOARD_SIZE + 1)]
        for r in range(1, BOARD_SIZE + 1)
    ]
    cols = [
        [position(r, c) for r in range(1, BOARD_SIZE + 1)]
        for c in range(1, BOARD_SIZE + 1)
    ]
    if direction == "L":
        return list(zip(ROW_STATUSES, rows))
    if direction == "R":
        return [(s, list(reversed(line))) for s, line in zip(ROW_STATUSES, rows)]
    if direction == "U":
        return list(zip(COL_STATUSES, cols))
    if direction == "D":
        return [(s, list(reversed(line))) for s, line in zip(COL_STATUSES, cols)]
    raise ValueError(f"Unknown direction {direction}")


class TwentyFortyEightGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        # only the IPC variant exists for now, more can be added here later
        mapping["variant"] = Categorical(
            "variant",
            ["ipc"],
            default="ipc",
        )
        return ConfigurationSpace(name=mapping)

    def __init__(self, domain_params: Configuration):
        domain_params.check_valid_configuration()
        if (
            domain_params.config_space
            != TwentyFortyEightGenerator.get_domain_parameter_space()
        ):
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._value = self._domain.fluent("value")
        self._pos_at = self._domain.fluent("pos-at")
        self._next = self._domain.fluent("next")
        self._next_idx = self._domain.fluent("next-idx")
        self._start_status = self._domain.fluent("start-status")
        self._free_to_play = self._domain.fluent("free-to-play")

        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant != "ipc":
            raise ValueError(f"invalid variant {self.variant}")
        # The value the goal asks for at p11, written as the tile itself (128,
        # 256, ...) rather than as an exponent, because that is how the goal
        # of every shipped instance reads. It has to equal the sum of the
        # board, see check_instance_parameters.
        #
        # NOTE that makes this space impractical to draw from at random: a
        # goal_tile picked independently of the 16 tiles practically never
        # matches their sum, so `sample()` over the full space spins in its
        # rejection loop. Build boards deliberately - as sets/ does - or
        # sample a space that pins goal_tile and lets the tiles add up to it.
        mapping["goal_tile"] = Integer("goal_tile", (0, MAX_INT), default=128)
        # One parameter per cell, holding that tile as a power of two:
        # 0 is an empty cell and k stands for 2^k. The defaults spell out
        # pfile8, the smallest instance of the set.
        defaults = {
            "tile_11": 2,
            "tile_13": 5,
            "tile_14": 1,
            "tile_21": 2,
            "tile_23": 1,
            "tile_32": 5,
            "tile_41": 5,
            "tile_42": 2,
            "tile_44": 4,
        }
        for row in range(1, BOARD_SIZE + 1):
            for col in range(1, BOARD_SIZE + 1):
                name = tile_parameter(row, col)
                mapping[name] = Integer(
                    name, (0, MAX_TILE_EXPONENT), default=defaults.get(name, 0)
                )
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"2048 V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            # No metric: none of the 20 shipped instances defines one.
            return reader.parse_problem(
                str(RESOURCES_PATH / f"twenty_forty_eight_v{self.version}.pddl")
            )
        raise ValueError(f"Unknown domain version {self.version}")

    def _get_object(self, name: str) -> Object:
        # Every object of this domain is a :constant of the domain file, so
        # they already exist on the skeleton and instances never add any.
        #
        # The names are lowercased because the PDDL reader lowercases them:
        # the domain writes the directions as "L R U D" but the parsed problem
        # calls them "l r u d". Every other name is already lowercase.
        return self._domain.object(name.lower())

    def _check_params(self, params: Configuration) -> None:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

    def _board(self, params: Configuration) -> List[Tuple[str, int]]:
        """The board as (position, tile value) pairs, row by row."""
        return [
            (position(r, c), tile_value(params[tile_parameter(r, c)]))
            for r in range(1, BOARD_SIZE + 1)
            for c in range(1, BOARD_SIZE + 1)
        ]

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        # The domain declares every position, status, direction and index as a
        # :constant, so an instance adds nothing of its own.
        return []

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        # Fixed by the domain file rather than by the instance space: the
        # board is always 4x4 and the statuses, directions and indices that
        # drive the phase machine are always the same.
        return list(self._domain.all_objects)

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        # Every shipped goal is the whole board emptied into one tile at p11.
        return [
            Equals(
                self._value(self._get_object(pos)),
                params["goal_tile"] if pos == GOAL_POSITION else 0,
            )
            for pos, _ in self._board(params)
        ]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        res: dict[FNode, FNode] = {}
        indices = [f"i{i}" for i in range(1, BOARD_SIZE + 1)]

        # Which board position each (direction, row/column, index) refers to,
        # and the order the rows or columns are swept in. This scaffolding is
        # identical in all 20 shipped instances.
        for direction in DIRECTIONS:
            lines = board_lines(direction)
            for status, line in lines:
                for index, pos in zip(indices, line):
                    res[
                        self._pos_at(
                            self._get_object(direction),
                            self._get_object(status),
                            self._get_object(index),
                            self._get_object(pos),
                        )
                    ] = TRUE()
            statuses = [status for status, _ in lines] + [DONE_STATUS]
            for current, following in zip(statuses, statuses[1:]):
                res[
                    self._next(
                        self._get_object(direction),
                        self._get_object(current),
                        self._get_object(following),
                    )
                ] = TRUE()
            res[
                self._start_status(
                    self._get_object(direction), self._get_object(statuses[0])
                )
            ] = TRUE()

        # The chain the combine phase walks to pair up neighbouring cells.
        for current, following in zip(indices, indices[1:]):
            res[
                self._next_idx(self._get_object(current), self._get_object(following))
            ] = TRUE()

        # The board starts between moves, ready for a direction to be chosen.
        res[self._free_to_play()] = TRUE()

        for pos, value in self._board(params):
            res[self._value(self._get_object(pos))] = value
        return res

    def check_instance_parameters(self, params: Configuration):
        # Shifting only moves tiles around and a merge turns two tiles of
        # value v into one of value 2v, so the sum of the board never changes.
        # The goal empties the board into a single tile, so that tile has to
        # be worth exactly what the board is worth. All 20 shipped instances
        # satisfy this.
        total = sum(value for _, value in self._board(params))
        if total != params["goal_tile"]:
            return False
        # A single tile is always a power of two: every tile starts as one and
        # merging doubles it. So a board whose total is not a power of two can
        # never be collected into one tile, whatever the moves.
        #
        # NOTE this is necessary but not sufficient - the merges also have to
        # be reachable from where the tiles actually sit, which is the hard
        # part of the puzzle and is left to the planner.
        return total > 0 and total & (total - 1) == 0
