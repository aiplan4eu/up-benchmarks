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

from .resources.ipc_onlycraft_data import IPC_INSTANCES


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"


def _trees_needed(n_pogo_sticks: int, tapped: int, synthetic: int) -> int:
    """Count the trees one particular plan needs to make n_pogo_sticks.

    The plan makes `tapped` of the pellets with tree taps, `synthetic` (0 or 1)
    with CRAFT_SYNTHETIC_PELLETS, and the rest by smelting. Everything is
    counted in whole crafts: planks and sticks are made 4 at a time, and a tree
    is broken for 2 logs at once.
    """
    # the pellets still missing, made by SMELT_PELLETS_RAW at 4 logs each
    smelted = max(0, n_pogo_sticks - tapped - synthetic)
    # 4 sticks per pogo stick, plus 1 per tree tap
    sticks = 4 * n_pogo_sticks + tapped
    # 2 planks per pogo stick, 5 per tree tap, and 2 for every 4 sticks
    planks = 2 * n_pogo_sticks + 5 * tapped + 2 * ceil(sticks / 4)
    # 1 log for every 4 planks, 4 per smelted pellet, 1 for the synthetic one
    logs = ceil(planks / 4) + 4 * smelted + synthetic
    # Every tree that is not tapped is broken with BREAK_BRUTAL for 2 logs. A
    # tapped tree gives no logs at all, so it is counted on top.
    return ceil(logs / 2) + tapped


def min_trees_for(n_pogo_sticks: int) -> int:
    """Return the fewest trees from which n_pogo_sticks pogo sticks can be made.

    A pogo stick needs 2 planks, 4 sticks and a pellet. There are three ways to
    make a pellet. Priced in logs, with a tree worth the 2 logs BREAK_BRUTAL
    gets from it (BREAK only gets 1):
      - a tree tap: 5 planks and 1 stick (1.375 logs), plus the tree it is
        placed on, which then gives no logs (2 more) - 3.375 logs in all;
      - smelting: SMELT_PELLETS_RAW turns 2 logs into half a pellet - 4 logs;
      - CRAFT_SYNTHETIC_PELLETS: 1 log, but only once per instance, because it
        raises the toxicity, which never goes down, and CRAFT_WOODEN_POGO needs
        the toxicity to be at most 1.

    The planks and sticks of the pogo stick itself cost 1 log, half a tree.

    So the cheapest plan uses the synthetic pellet once (1 tree for that pogo
    stick) and taps a tree for every other pellet (2.1875 trees per pogo
    stick). Those are averages: planks and sticks are made 4 at a time and a
    tree gives its 2 logs at once, so the real count rounds up, sometimes by a
    whole tree. _trees_needed counts that plan with every rounding step.
    """
    return _trees_needed(n_pogo_sticks, max(0, n_pogo_sticks - 1), 1)


class OnlyCraftGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        mapping["variant"] = Categorical(
            "variant",
            ["generic", "ipc"],
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
        if self.variant not in ("generic", "ipc"):
            raise ValueError(f"invalid variant {self.variant}")
        if self.variant == "ipc":
            # Which IPC instance, by position in name order with the opt
            # track first: P01_opt is 1, P01_sat is 21. Both tracks reuse the
            # numbers 01-20 in their file names.
            indices = sorted(IPC_INSTANCES)
            mapping["index"] = Integer(
                "index", (indices[0], indices[-1]), default=indices[0]
            )
            return ConfigurationSpace(name=mapping)
        mapping["n_pogo_sticks"] = Integer("n_pogo_sticks", (1, MAX_INT), default=1)
        # How many extra trees there are beyond the fewest the goal can be met with.
        mapping["extra_trees"] = Integer("extra_trees", (0, MAX_INT), default=3)
        # How many low trees there are, these are always extra.
        mapping["n_low_trees"] = Integer("n_low_trees", (0, MAX_INT), default=0)
        # How many empty cells there are, these are just objects bloat.
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
        if self.variant == "ipc":
            return IPC_INSTANCES[params["index"]]["n_cells"]
        return self._n_trees(params) + params["n_low_trees"] + params["n_air_cells"]

    def _n_pogo_sticks(self, params: Configuration) -> int:
        if self.variant == "ipc":
            return IPC_INSTANCES[params["index"]]["n_pogo_sticks"]
        return params["n_pogo_sticks"]

    def _layout(self, params: Configuration) -> Tuple[Set[int], Set[int], int, int]:
        """Return (low tree cells, air cells, start cell, crafting table cell),
        by cell number.

        Every cell that is neither a low tree nor air is a tree.
        """
        if self.variant == "ipc":
            entry = IPC_INSTANCES[params["index"]]
            return set(), set(entry["air"]), entry["position"], entry["crafting_table"]
        # The IPC instances scatter the trees over the cells, but no action
        # reads which cell is which: (position ?c) and (connected ?a ?b) are
        # declared and never used, and (air_cell ?c) only ever appears as an
        # effect.
        #
        # The generic variant lays the cells out in order - trees, then low trees,
        # then air and puts the start and the crafting table on cell0.
        n_trees = self._n_trees(params)
        n_low = params["n_low_trees"]
        low = set(range(n_trees, n_trees + n_low))
        air = set(range(n_trees + n_low, self._n_cells(params)))
        return low, air, 0, 0

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
        if self.variant == "ipc":
            first, last = hyperparam_range(instance_parameters_space["index"])
            n_cells = max(
                IPC_INSTANCES[i]["n_cells"] for i in IPC_INSTANCES if first <= i <= last
            )
            return [self._cell(i) for i in range(n_cells)]
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
        return [GE(self._count_pogo_stick(), self._n_pogo_sticks(params))]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        cells = self.get_objects(params)
        low, air, start, crafting_table = self._layout(params)

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
        # and the start. The crafting table is never removed, so a tree cell
        # can hold it just as well.
        res[self._crafting_table_cell(cells[crafting_table])] = TRUE()
        res[self._position(cells[start])] = TRUE()
        return res

    def check_instance_parameters(self, params: Configuration):
        if self.variant == "ipc":
            return params["index"] in IPC_INSTANCES
        # Every generic instance is solvable by construction: it has at least
        # min_trees_for(n_pogo_sticks) trees, and low trees and air cells can
        # only add to what a plan has.
        return True
