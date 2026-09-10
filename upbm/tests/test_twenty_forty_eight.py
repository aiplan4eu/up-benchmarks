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

from typing import Any, Dict, List, Tuple

from ConfigSpace import Configuration

from unified_planning.engines.plan_validator import (
    SequentialPlanValidator,
    ValidationResultStatus,
)

from upbm.domains.twenty_forty_eight import TwentyFortyEightGenerator
from upbm.domains.twenty_forty_eight.twenty_forty_eight import (
    BOARD_SIZE,
    board_lines,
    position,
    tile_parameter,
    tile_value,
)
from upbm.io import parse_plan_string
from upbm.tests.base_domain_test import BaseDomainTest


# pfile8, the smallest instance of the IPC set: nine tiles adding up to 128.
PFILE8_BOARD = [
    [4, 0, 32, 2],
    [4, 0, 2, 0],
    [0, 32, 0, 0],
    [32, 4, 0, 16],
]

# pfile20, a full board adding up to 8192.
PFILE20_BOARD = [
    [32, 2048, 256, 1024],
    [256, 64, 1024, 512],
    [256, 128, 512, 256],
    [256, 32, 1024, 512],
]

# The two 2s of the smallest board we can build by hand: they merge into one 4.
TINY_BOARD = [
    [2, 2, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
]

ROW_ORDER = ["top", "midtop", "midbot", "bot"]
IDX_ORDER = ["i1", "i2", "i3", "i4"]


def board_params(board: List[List[int]]) -> Dict[str, int]:
    """Turn a board of tile values into the tile_rc parameters holding it."""
    params = {}
    for r in range(1, BOARD_SIZE + 1):
        for c in range(1, BOARD_SIZE + 1):
            value = board[r - 1][c - 1]
            params[tile_parameter(r, c)] = 0 if value == 0 else value.bit_length() - 1
    return params


def board_total(board: List[List[int]]) -> int:
    return sum(v for row in board for v in row)


class TestTwentyFortyEight(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self) -> str:
        return "2048"

    @property
    def generator(self) -> Any:
        return TwentyFortyEightGenerator

    def _get_configs(
        self, board: List[List[int]], goal_tile: Any = None
    ) -> Tuple[Configuration, Configuration]:
        """A (domain config, instance config) pair holding the given board."""
        domain_space = TwentyFortyEightGenerator.get_domain_parameter_space()
        domain_config = Configuration(
            domain_space, values={"version": 1, "variant": "ipc"}
        )
        gen = TwentyFortyEightGenerator(domain_config)
        values: Dict[str, Any] = dict(board_params(board))
        values["goal_tile"] = board_total(board) if goal_tile is None else goal_tile
        return domain_config, Configuration(gen.instance_parameter_space, values=values)

    def _instance(self, board: List[List[int]], goal_tile: Any = None):
        domain_config, instance_config = self._get_configs(board, goal_tile)
        return TwentyFortyEightGenerator(domain_config).get_instance(instance_config)

    def _true_facts(self, problem, fluent_name: str) -> List[Tuple[str, ...]]:
        return [
            tuple(str(a) for a in k.args)
            for k, v in problem.explicit_initial_values.items()
            if k.fluent().name == fluent_name
            and v.is_bool_constant()
            and v.bool_constant_value()
        ]

    @property
    def plannable(self) -> List[Tuple[Configuration, Configuration]]:
        # Deliberately not an IPC instance: the shipped ones are hard by
        # design, this one is a single merge.
        return [self._get_configs(TINY_BOARD)]

    @property
    def object_data(self):
        # The domain declares every object as a :constant, so the counts are
        # the same for every instance: 16 cells, 9 statuses (4 rows, 4 columns
        # and "done"), 4 directions and 4 indices.
        domain_config, instance_config = self._get_configs(PFILE8_BOARD)
        return [
            (
                domain_config,
                instance_config,
                [("pos", 16), ("status", 9), ("direction", 4), ("idx", 4)],
            )
        ]

    @property
    def problem_actions(self) -> List[Tuple[Configuration, Configuration, int]]:
        domain_config, instance_config = self._get_configs(PFILE8_BOARD)
        # play, 16 shift patterns, 2 shift finishes and 4 combine actions
        return [(domain_config, instance_config, 23)]

    def test_board_is_the_tile_parameters(self):
        """Each tile_rc exponent lands as 2^k on the matching cell."""
        problem = self._instance(PFILE8_BOARD)
        value = problem.fluent("value")
        for r in range(1, BOARD_SIZE + 1):
            for c in range(1, BOARD_SIZE + 1):
                cell = value(problem.object(position(r, c)))
                self.assertEqual(
                    int(problem.explicit_initial_values[cell].constant_value()),
                    PFILE8_BOARD[r - 1][c - 1],
                    f"wrong tile at {position(r, c)}",
                )
        # exponent 0 is the empty cell and never the value 1, which the game
        # has no tile for
        self.assertEqual(tile_value(0), 0)
        self.assertEqual([tile_value(k) for k in (1, 2, 5, 11)], [2, 4, 32, 2048])

    def test_scaffolding_matches_the_ipc_set(self):
        """The pos-at / next / next-idx facts are the shipped ones.

        This scaffolding is identical in all 20 shipped instances, so it is
        generated from a rule rather than stored. The literals below are read
        off pfile8 and are what pins that rule down.
        """
        problem = self._instance(PFILE8_BOARD)
        pos_at = set(self._true_facts(problem, "pos-at"))

        # one line per direction, copied from the shipped file: shifting left
        # walks a row from its left-hand cell, right walks it backwards, and
        # up/down do the same over a column
        for direction, status, cells in [
            ("l", "top", ["p11", "p12", "p13", "p14"]),
            ("r", "top", ["p14", "p13", "p12", "p11"]),
            ("u", "left", ["p11", "p21", "p31", "p41"]),
            ("d", "left", ["p41", "p31", "p21", "p11"]),
        ]:
            for index, cell in zip(IDX_ORDER, cells):
                self.assertIn((direction, status, index, cell), pos_at)

        # all 64 mappings are present, and each direction covers every cell
        # exactly once
        self.assertEqual(len(pos_at), 64)
        for direction in ("l", "r", "u", "d"):
            cells = [f[3] for f in pos_at if f[0] == direction]
            self.assertEqual(sorted(cells), sorted(set(cells)))
            self.assertEqual(len(cells), 16)

        # the sweep order of each direction, ending in "done"
        self.assertEqual(
            sorted(self._true_facts(problem, "next")),
            sorted(
                (d, a, b)
                for d, statuses in [
                    ("l", ROW_ORDER),
                    ("r", ROW_ORDER),
                    ("u", ["left", "midleft", "midright", "right"]),
                    ("d", ["left", "midleft", "midright", "right"]),
                ]
                for a, b in zip(statuses, statuses[1:] + ["done"])
            ),
        )
        self.assertEqual(
            sorted(self._true_facts(problem, "start-status")),
            [("d", "left"), ("l", "top"), ("r", "top"), ("u", "left")],
        )
        self.assertEqual(
            sorted(self._true_facts(problem, "next-idx")),
            [("i1", "i2"), ("i2", "i3"), ("i3", "i4")],
        )
        # the board starts between moves
        self.assertEqual(len(self._true_facts(problem, "free-to-play")), 1)

    def test_right_and_down_reverse_their_lines(self):
        """The four directions sweep the same cells in mirrored orders."""
        for forward, backward in [("L", "R"), ("U", "D")]:
            for (_, a), (_, b) in zip(board_lines(forward), board_lines(backward)):
                self.assertEqual(a, list(reversed(b)))
        # left walks rows, up walks columns
        self.assertEqual(board_lines("L")[0][1], ["p11", "p12", "p13", "p14"])
        self.assertEqual(board_lines("U")[0][1], ["p11", "p21", "p31", "p41"])

    def test_goal_collects_the_board_into_p11(self):
        """Every shipped goal is one tile at p11 and an empty board around it."""
        problem = self._instance(PFILE8_BOARD)
        goals = {str(g) for g in problem.goals}
        self.assertIn("(value(p11) == 128)", goals)
        self.assertEqual(len(goals), 16)
        for r in range(1, BOARD_SIZE + 1):
            for c in range(1, BOARD_SIZE + 1):
                if (r, c) != (1, 1):
                    self.assertIn(f"(value({position(r, c)}) == 0)", goals)

    def test_shipped_boards_are_reproduced(self):
        """Two shipped instances, pinned against values read off the dataset."""
        for board, goal in [(PFILE8_BOARD, 128), (PFILE20_BOARD, 8192)]:
            problem = self._instance(board)
            value = problem.fluent("value")
            self.assertEqual(board_total(board), goal)
            self.assertIn(f"(value(p11) == {goal})", {str(g) for g in problem.goals})
            for r in range(1, BOARD_SIZE + 1):
                for c in range(1, BOARD_SIZE + 1):
                    cell = value(problem.object(position(r, c)))
                    self.assertEqual(
                        int(problem.explicit_initial_values[cell].constant_value()),
                        board[r - 1][c - 1],
                    )

    def test_board_sum_must_equal_the_goal_tile(self):
        """A merge conserves the board sum, so the goal tile is forced."""
        domain_config, _ = self._get_configs(PFILE8_BOARD)
        gen = TwentyFortyEightGenerator(domain_config)
        _, good = self._get_configs(PFILE8_BOARD, goal_tile=128)
        self.assertTrue(gen.check_instance_parameters(good))
        for wrong in (64, 256):
            _, bad = self._get_configs(PFILE8_BOARD, goal_tile=wrong)
            self.assertFalse(
                gen.check_instance_parameters(bad),
                f"goal {wrong} does not match the board sum but was accepted",
            )
        # and an instance that does not add up is refused rather than built
        with self.assertRaises(ValueError):
            gen.get_instance(bad)

    def test_a_sum_that_is_not_a_power_of_two_is_rejected(self):
        """One tile is always a power of two, so the sum has to be one too."""
        domain_config, _ = self._get_configs(PFILE8_BOARD)
        gen = TwentyFortyEightGenerator(domain_config)
        # 2 + 4 = 6 cannot be collected into a single tile
        odd_board = [[2, 4, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
        _, params = self._get_configs(odd_board)
        self.assertEqual(board_total(odd_board), 6)
        self.assertFalse(gen.check_instance_parameters(params))
        # an empty board asks for nothing and is refused as degenerate
        _, empty = self._get_configs([[0] * 4 for _ in range(4)])
        self.assertFalse(gen.check_instance_parameters(empty))

    def test_shipped_goal_tiles_are_accepted(self):
        """Every goal tile the IPC set uses is a legal target."""
        domain_config, _ = self._get_configs(PFILE8_BOARD)
        gen = TwentyFortyEightGenerator(domain_config)
        # the goals of the 20 shipped instances, deduplicated
        for goal in (128, 256, 512, 1024, 2048, 4096, 8192):
            board = [[0] * 4 for _ in range(4)]
            # any board adding up to the goal will do here
            board[0][0] = goal
            _, params = self._get_configs(board)
            self.assertTrue(
                gen.check_instance_parameters(params), f"goal {goal} was rejected"
            )

    def test_instances_add_no_objects(self):
        """The board is fixed by the domain, which declares it as :constants."""
        domain_config, instance_config = self._get_configs(PFILE8_BOARD)
        gen = TwentyFortyEightGenerator(domain_config)
        self.assertEqual(list(gen.get_objects(instance_config)), [])
        # they are all there anyway, carried over from the skeleton
        problem = gen.get_instance(instance_config)
        self.assertEqual(len(list(problem.all_objects)), 33)
        self.assertEqual(
            sorted(o.name for o in gen.object_universe()),
            sorted(o.name for o in problem.all_objects),
        )

    def test_sequential_plan_validation(self):
        """Walk one whole move by hand: shift, combine, shift again.

        Two 2s side by side in the top row become a single 4 at p11. The plan
        covers the whole phase machine - the first shift sweep, the combine
        sweep pair by pair down every row, and the second shift sweep.
        """
        problem = self._instance(TINY_BOARD)
        sweep = list(zip(ROW_ORDER, ROW_ORDER[1:] + ["done"]))
        lines = ["(play l top)"]
        for i, (current, following) in enumerate(sweep):
            cells = " ".join(position(i + 1, c) for c in range(1, BOARD_SIZE + 1))
            # only the top row holds anything, and it is already packed
            pattern = "1100" if i == 0 else "0000"
            lines.append(f"(shift-{pattern} {cells} {current} {following} l)")
        lines.append("(shift-finish-to-combine l top)")
        for i, (current, following) in enumerate(sweep):
            for j in range(BOARD_SIZE - 1):
                lines.append(
                    f"(combine-match l {current} {IDX_ORDER[j]} {IDX_ORDER[j + 1]} "
                    f"{position(i + 1, j + 1)} {position(i + 1, j + 2)})"
                )
            lines.append(f"(combine-row-advance l {current} {following})")
        lines.append("(combine-finish l top)")
        for i, (current, following) in enumerate(sweep):
            cells = " ".join(position(i + 1, c) for c in range(1, BOARD_SIZE + 1))
            # the merged 4 now sits alone at p11
            pattern = "1000" if i == 0 else "0000"
            lines.append(f"(shift-{pattern} {cells} {current} {following} l)")
        lines.append("(shift-finish l)")

        plan = parse_plan_string(problem, "\n".join(lines))
        self.assertEqual(len(plan.actions), 28)
        with SequentialPlanValidator() as validator:
            result = validator.validate(problem, plan)
            self.assertEqual(result.status, ValidationResultStatus.VALID, f"{result}")

    def test_a_plan_may_stop_once_the_board_is_right(self):
        """The goal only talks about tile values, never about the phase.

        So a plan does not have to finish the move it started: as soon as the
        merge has happened the board already satisfies the goal. This is why a
        planner returns 7 actions where the full move takes 28.
        """
        problem = self._instance(TINY_BOARD)
        plan = parse_plan_string(
            problem,
            "\n".join(
                [
                    "(play l top)",
                    "(shift-1100 p11 p12 p13 p14 top midtop l)",
                    "(shift-0000 p21 p22 p23 p24 midtop midbot l)",
                    "(shift-0000 p31 p32 p33 p34 midbot bot l)",
                    "(shift-0000 p41 p42 p43 p44 bot done l)",
                    "(shift-finish-to-combine l top)",
                    "(combine-match l top i1 i2 p11 p12)",
                ]
            ),
        )
        with SequentialPlanValidator() as validator:
            result = validator.validate(problem, plan)
            self.assertEqual(result.status, ValidationResultStatus.VALID, f"{result}")
