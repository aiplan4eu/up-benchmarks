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

from math import ceil
from pathlib import Path
from typing import Any, Optional, List, Set, Tuple

from ConfigSpace import (
    ConfigurationSpace,
    Configuration,
    Integer,
    Categorical,
    Constant,
)
from unified_planning.io import PDDLReader
from unified_planning.model import Problem, Object, FNode
from unified_planning.shortcuts import TRUE, GE

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"


def _trees_needed(n_pogo_sticks: int, tapped: int, synthetic: int) -> int:
    """Trees used by one way of making n_pogo_sticks: `tapped` of the pellets
    come from tree taps, `synthetic` (0 or 1) from CRAFT_SYNTHETIC_PELLETS, and
    the rest from SMELT_PELLETS_RAW. See min_trees_for for the recipes."""
    smelted = max(0, n_pogo_sticks - tapped - synthetic)
    sticks = 4 * n_pogo_sticks + tapped
    planks = 2 * n_pogo_sticks + 5 * tapped + 2 * ceil(sticks / 4)
    logs = ceil(planks / 4) + 4 * smelted + synthetic
    return ceil(logs / 2) + tapped


def min_trees_for(n_pogo_sticks: int) -> int:
    """Return the fewest trees from which n_pogo_sticks pogo sticks can be made.

    A pogo stick takes 2 planks, 4 sticks and 1 pellet. A log makes 4 planks,
    2 planks make 4 sticks. A tree is either broken with BREAK_BRUTAL for 2
    logs (BREAK gives only 1) or used up by PLACE_TREE_TAP for 1 pellet, which
    first needs a tree tap (5 planks and 1 stick). Otherwise a pellet costs 4
    logs by SMELT_PELLETS_RAW (2 logs for half a pellet), or 1 log by
    CRAFT_SYNTHETIC_PELLETS - but only once per instance, since that raises the
    toxicity, which never goes down, and CRAFT_WOODEN_POGO needs it at most 1.

    Tapping is the cheapest route, so the best plan taps the trees for all but
    a few of the pellets. Only that end is searched: checked against a search
    over every number of tapped trees for each goal up to 5000, and the counts
    repeat every 16 pogo sticks (16 more of them take exactly 35 more trees),
    so that covers every goal. An exhaustive search over the actions themselves
    confirmed that one tree fewer is unsolvable, for goals 1 to 6.
    """
    return min(
        _trees_needed(n_pogo_sticks, tapped, synthetic)
        for synthetic in (0, 1)
        for tapped in range(max(0, n_pogo_sticks - 8), n_pogo_sticks + 1)
    )


class OnlyCraftGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        # Only the generic variant exists for now, more can be added here
        # later. The opt/sat split of the dataset is not a variant: the two
        # tracks share one domain file and differ only in their instances.
        mapping["variant"] = Categorical(
            "variant",
            ["generic"],
            default="generic",
        )
        return ConfigurationSpace(name=mapping)

    def __init__(self, domain_params: Configuration):
        domain_params.check_valid_configuration()
        if (
            domain_params.config_space
            != OnlyCraftGenerator.get_domain_parameter_space()
        ):
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._Cell = self._domain.user_type("cell")
        self._position = self._domain.fluent("position")
        self._tree_cell = self._domain.fluent("tree_cell")
        self._low_tree_cell = self._domain.fluent("low_tree_cell")
        self._air_cell = self._domain.fluent("air_cell")
        self._crafting_table_cell = self._domain.fluent("crafting_table_cell")
        self._toxicity = self._domain.fluent("toxicity")
        self._count_pogo_stick = self._domain.fluent("count_pogo_stick")
        # the five inventory counters that all start empty
        self._inventory = [
            self._domain.fluent(f"count_{item}_in_inventory")
            for item in [
                "log",
                "planks",
                "stick",
                "sack_polyisoprene_pellets",
                "tree_tap",
            ]
        ]

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant != "generic":
            raise ValueError(f"invalid variant {self.variant}")
        # The goal, (>= (count_pogo_stick) n_pogo_sticks).
        mapping["n_pogo_sticks"] = Integer("n_pogo_sticks", (1, MAX_INT), default=1)
        # How many trees there are beyond the fewest the goal can be met with
        # (min_trees_for), so every value is solvable and 0 is the tightest
        # instance there is: a plan then has to find the right mix of tapping,
        # smelting and the one synthetic pellet. The shipped instances are far
        # from tight - they have (7k + 1) // 2 trees, about 1.6 times the
        # minimum - which is where the default of 3 comes from: it is what that
        # rule gives for one pogo stick.
        mapping["extra_trees"] = Integer("extra_trees", (0, MAX_INT), default=3)
        # Low trees, which no shipped instance has. They are what BREAK_LOW
        # needs, half a log each, and PLACE_TREE_TAP cannot use them, so they
        # only ever add logs: they can make an instance easier, never unsolvable.
        mapping["n_low_trees"] = Integer("n_low_trees", (0, MAX_INT), default=0)
        # Cells that are neither: no action reads them, so they only add
        # objects for a planner to ground. 5 matches P01_opt with the defaults
        # above.
        mapping["n_air_cells"] = Integer("n_air_cells", (0, MAX_INT), default=5)
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"OnlyCraft V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            return reader.parse_problem(
                str(RESOURCES_PATH / f"onlycraft_v{self.version}.pddl")
            )
        raise ValueError(f"Unknown domain version {self.version}")

    def _get_object(self, name: str, type: Any):
        res = self._object_cache.get((name, type), None)
        if res is None:
            res = Object(name, type)
            self._object_cache[(name, type)] = res
        return res

    def _check_params(self, params: Configuration) -> None:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")

    def _cell(self, i: int) -> Object:
        return self._get_object(f"cell{i}", self._Cell)

    def _n_trees(self, params: Configuration) -> int:
        return min_trees_for(params["n_pogo_sticks"]) + params["extra_trees"]

    def _n_cells(self, params: Configuration) -> int:
        return self._n_trees(params) + params["n_low_trees"] + params["n_air_cells"]

    def _layout(self, params: Configuration) -> Tuple[Set[int], Set[int]]:
        """Return (low tree cells, air cells), by cell number.

        Every cell that is neither a low tree nor air is a tree.

        The shipped instances scatter the trees over the cells, but no action
        reads which cell is which: (position ?c) and (connected ?a ?b) are
        declared and never used, and (air_cell ?c) only ever appears as an
        effect. So the cells are laid out in order - trees, then low trees,
        then air - which loses nothing a plan could notice.
        """
        n_trees = self._n_trees(params)
        n_low = params["n_low_trees"]
        low = set(range(n_trees, n_trees + n_low))
        air = set(range(n_trees + n_low, self._n_cells(params)))
        return low, air

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        return [self._cell(i) for i in range(self._n_cells(params))]

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        # min_trees_for never decreases as the goal grows, so the largest goal
        # needs the most trees
        n_cells = sum(
            hyperparam_range(instance_parameters_space[name])[1]
            for name in ["extra_trees", "n_low_trees", "n_air_cells"]
        )
        _, most_pogo_sticks = hyperparam_range(
            instance_parameters_space["n_pogo_sticks"]
        )
        n_cells += min_trees_for(most_pogo_sticks)
        return [self._cell(i) for i in range(n_cells)]

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        return [GE(self._count_pogo_stick(), params["n_pogo_sticks"])]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        cells = self.get_objects(params)
        low, air = self._layout(params)

        res: dict[FNode, FNode] = {self._toxicity(): 0, self._count_pogo_stick(): 0}
        for fluent in self._inventory:
            res[fluent()] = 0
        for i, cell in enumerate(cells):
            if i in air:
                res[self._air_cell(cell)] = TRUE()
            elif i in low:
                res[self._low_tree_cell(cell)] = TRUE()
            else:
                res[self._tree_cell(cell)] = TRUE()
        # One crafting table, needed by CRAFT_TREE_TAP and CRAFT_WOODEN_POGO,
        # and the start, both on cell0 - as for the layout, nothing reads which
        # cell they are on. The crafting table is never removed, so a tree cell
        # can hold it just as well.
        res[self._crafting_table_cell(cells[0])] = TRUE()
        res[self._position(cells[0])] = TRUE()
        return res

    def check_instance_parameters(self, params: Configuration):
        # Every instance is solvable by construction: it has at least
        # min_trees_for(n_pogo_sticks) trees, and low trees and air cells can
        # only add to what a plan has.
        return True
