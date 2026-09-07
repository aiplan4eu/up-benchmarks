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
from typing import Any, Optional, List

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


def n_trees_for(n_pogo_sticks: int) -> int:
    """Return the number of tree cells of an instance.

    Every one of the 40 shipped instances (20 opt and 20 sat) has exactly
    ceil(3.5 * goal) trees, so the number of trees is not an independent
    parameter of the set: it follows from how many pogo sticks are asked for.
    3.5 trees per pogo stick is a comfortable margin, see
    check_instance_parameters for the actual cost of one pogo stick.
    """
    return (7 * n_pogo_sticks + 1) // 2


class OnlyCraftGenerator(Generator):
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
        if self.variant != "ipc":
            raise ValueError(f"invalid variant {self.variant}")
        mapping["n_cells"] = Integer("n_cells", (1, MAX_INT), default=9)
        # the goal, which also fixes the number of trees, see n_trees_for()
        mapping["n_pogo_sticks"] = Integer("n_pogo_sticks", (1, MAX_INT), default=1)
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

    def get_objects(self, params) -> List[Object]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        return [
            self._get_object(f"cell{i}", self._Cell) for i in range(params["n_cells"])
        ]

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        _, cells_upper = hyperparam_range(instance_parameters_space["n_cells"])
        return [self._get_object(f"cell{i}", self._Cell) for i in range(cells_upper)]

    def get_goal(self, params) -> List[FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")
        return [GE(self._count_pogo_stick(), params["n_pogo_sticks"])]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")
        cells = self.get_objects(params)
        n_trees = n_trees_for(params["n_pogo_sticks"])

        res: dict[FNode, FNode] = {self._toxicity(): 0, self._count_pogo_stick(): 0}
        for fluent in self._inventory:
            res[fluent()] = 0
        # The shipped instances scatter the trees over the cells, but no action
        # reads which cell is which: (position ?c) and (connected ?a ?b) are
        # declared and never used, and (air_cell ?c) only ever appears as an
        # effect. So the first cells are the trees and the rest is air, which
        # gives an instance equivalent to the shipped one.
        for cell in cells[:n_trees]:
            res[self._tree_cell(cell)] = TRUE()
        for cell in cells[n_trees:]:
            res[self._air_cell(cell)] = TRUE()
        # One crafting table, needed by CRAFT_TREE_TAP and CRAFT_WOODEN_POGO.
        # It is never removed, so a tree cell can hold it just as well.
        res[self._crafting_table_cell(cells[0])] = TRUE()
        res[self._position(cells[0])] = TRUE()
        return res

    def check_instance_parameters(self, params: Configuration):
        # The trees have to fit in the grid. Nothing else can make an instance
        # unsolvable: one pogo stick costs 2 planks and 4 sticks, which is 4
        # planks, so one log; plus one pellet, which is 4 more logs by smelting
        # them. BREAK_BRUTAL turns a tree into 2 logs, so 2.5 trees per pogo
        # stick are enough and n_trees_for() always leaves 3.5.
        return params["n_cells"] >= n_trees_for(params["n_pogo_sticks"])
