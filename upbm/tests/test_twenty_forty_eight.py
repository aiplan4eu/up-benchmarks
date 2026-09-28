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

from typing import Any, List, Tuple

from ConfigSpace import Configuration

from upbm.domains.twenty_forty_eight import TwentyFortyEightGenerator
from upbm.domains.twenty_forty_eight.twenty_forty_eight import BOARD_SIZE, position
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

ROW_ORDER = ["top", "midtop", "midbot", "bot"]
COL_ORDER = ["left", "midleft", "midright", "right"]
IDX_ORDER = ["i1", "i2", "i3", "i4"]


class TestTwentyFortyEight(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self) -> str:
        return "2048"

    @property
    def generator(self) -> Any:
        return TwentyFortyEightGenerator

    def _get_configs(self, index: int) -> Tuple[Configuration, Configuration]:
        """A (domain config, instance config) pair for one shipped instance."""
        domain_space = TwentyFortyEightGenerator.get_domain_parameter_space()
        domain_config = Configuration(
            domain_space, values={"version": 1, "variant": "ipc"}
        )
        gen = TwentyFortyEightGenerator(domain_config)
        return domain_config, Configuration(
            gen.instance_parameter_space, values={"index": index}
        )

    def _instance(self, index: int):
        domain_config, instance_config = self._get_configs(index)
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
        # Empty on purpose. Every instance this generator can build is one of
        # the twenty shipped ones, and those are hard by design: the smallest,
        # pfile8, takes ENHSP 15s for a 343-action plan, which is far past what
        # this list is meant to hold. There is no small board to offer until a
        # variant exists that can invent one.
        return []

    @property
    def object_data(self):
        # Both ends of the index range, which is what catches the table being
        # misread. The counts themselves are the same for every instance: the
        # domain declares every object as a :constant, so an instance adds
        # none - 16 cells, 9 statuses (4 rows, 4 columns and "done"), 4
        # directions and 4 indices.
        counts = [("pos", 16), ("status", 9), ("direction", 4), ("idx", 4)]
        return [
            (*self._get_configs(8), counts),
            (*self._get_configs(29), counts),
        ]

    @property
    def problem_actions(self) -> List[Tuple[Configuration, Configuration, int]]:
        # play, 16 shift patterns, 2 shift finishes and 4 combine actions
        return [(*self._get_configs(8), 23)]

    def test_scaffolding_matches_the_ipc_set(self):
        """The pos-at / next / next-idx facts are the shipped ones.

        This scaffolding is identical in all 20 shipped instances, so the
        generator builds it from a rule instead of storing it in the table.
        The literals below are read off pfile8 and are what pins that rule
        down.
        """
        problem = self._instance(8)
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
                    ("u", COL_ORDER),
                    ("d", COL_ORDER),
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

    def test_shipped_boards_are_reproduced(self):
        """Two shipped boards, pinned against values read off the dataset.

        The boards are transcribed rather than derived, so this is the check
        that the table says what the shipped files say - one small instance and
        one full board, the ends of the range being covered by `object_data`.
        """
        for index, board, goal in [(8, PFILE8_BOARD, 128), (20, PFILE20_BOARD, 8192)]:
            problem = self._instance(index)
            value = problem.fluent("value")
            self.assertEqual(sum(v for row in board for v in row), goal)
            self.assertIn(f"(value(p11) == {goal})", {str(g) for g in problem.goals})
            for r in range(1, BOARD_SIZE + 1):
                for c in range(1, BOARD_SIZE + 1):
                    cell = value(problem.object(position(r, c)))
                    self.assertEqual(
                        int(problem.explicit_initial_values[cell].constant_value()),
                        board[r - 1][c - 1],
                    )
