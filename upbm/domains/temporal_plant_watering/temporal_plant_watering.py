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
    ForbiddenGreaterThanRelation,
)
from unified_planning.io import PDDLReader
from unified_planning.model import Problem, Object, FNode
from unified_planning.model.metrics import MinimizeMakespan
from unified_planning.shortcuts import TRUE, Equals

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"


def agent_cells(n_agents: int) -> List[tuple[int, int]]:
    """Return the (x, y) cell each agent starts on.

    The agents start one per cell up the left column, from the bottom-left
    corner (1, 1).
    """
    return [(1, y) for y in range(1, n_agents + 1)]


def plant_cells(size: int, n_agents: int, n_plants: int) -> List[tuple[int, int]]:
    """Return the (x, y) cell of each plant on a `size` x `size` grid.

    The plants go on the border of the grid, skipping the cells the agents
    start on. The border is walked clockwise from the top-left corner: the top
    row left to right, the right column downwards, the bottom row right to left
    and the left column upwards.
    """
    border = (
        [(x, size) for x in range(1, size + 1)]
        + [(size, y) for y in range(size - 1, 0, -1)]
        + [(x, 1) for x in range(size - 1, 0, -1)]
        + [(1, y) for y in range(2, size)]
    )
    taken = set(agent_cells(n_agents))
    return [cell for cell in border if cell not in taken][:n_plants]


class TemporalPlantWateringGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        mapping["variant"] = Categorical(
            "variant",
            ["border"],
            default="border",
        )
        return ConfigurationSpace(name=mapping)

    def __init__(self, domain_params: Configuration):
        domain_params.check_valid_configuration()
        if (
            domain_params.config_space
            != TemporalPlantWateringGenerator.get_domain_parameter_space()
        ):
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._Agent = self._domain.user_type("agent")
        self._Plant = self._domain.user_type("plant")
        self._Pump = self._domain.user_type("pump")
        self._pump_closed = self._domain.fluent("pump_closed")
        self._free = self._domain.fluent("free")
        self._handfree = self._domain.fluent("handfree")
        self._maxx = self._domain.fluent("maxx")
        self._maxy = self._domain.fluent("maxy")
        self._minx = self._domain.fluent("minx")
        self._miny = self._domain.fluent("miny")
        self._water_reserve = self._domain.fluent("water_reserve")
        self._x = self._domain.fluent("x")
        self._y = self._domain.fluent("y")
        self._plant_x = self._domain.fluent("plant_x")
        self._plant_y = self._domain.fluent("plant_y")
        self._tap_x = self._domain.fluent("tap_x")
        self._tap_y = self._domain.fluent("tap_y")
        self._poured = self._domain.fluent("poured")

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant != "border":
            raise ValueError(f"invalid variant {self.variant}")
        mapping["size"] = Integer("size", (2, MAX_INT), default=10)
        mapping["n_plants"] = Integer("n_plants", (1, MAX_INT), default=1)

        # The units of water each plant must receive.
        mapping["pour"] = Integer("pour", (1, MAX_INT), default=1)

        # One agent can never water anything: the pump is opened by an agent
        # with free hands while it is in use, and only taking the pump puts it
        # in use, which leaves the taker's hands full. So it takes one agent to
        # carry the pump to a plant and another to open it at the tap.
        mapping["n_agents"] = Integer("n_agents", (2, MAX_INT), default=2)

        mapping["tap_x"] = Integer("tap_x", (1, MAX_INT), default=4)
        mapping["tap_y"] = Integer("tap_y", (1, MAX_INT), default=4)
        space = ConfigurationSpace(name=mapping)

        # The agents and the pump must fit on the grid. As clauses, sampling
        # never draws an instance that breaks them, and a set file asking for
        # one fails naming the rule. check_instance_parameters repeats them,
        # because a reduced space from get_reduced_instance_space keeps only
        # the parameters, not these clauses.
        for name in ("n_agents", "tap_x", "tap_y"):
            space.add(ForbiddenGreaterThanRelation(space[name], space["size"]))
        return space

    @property
    def name(self) -> str:
        return f"Temporal Plant Watering V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            domain = reader.parse_problem(
                str(RESOURCES_PATH / f"temporal_plant_watering_v{self.version}.pddl")
            )
            domain.add_quality_metric(MinimizeMakespan())
            return domain
        raise ValueError(f"Unknown domain version {self.version}")

    def _get_object(self, name: str, type: Any):
        res = self._object_cache.get((name, type), None)
        if res is None:
            res = Object(name, type)
            self._object_cache[(name, type)] = res
        return res

    def _agents(self, n_agents: int) -> List[Object]:
        return [self._get_object(f"agent{i + 1}", self._Agent) for i in range(n_agents)]

    def _plants(self, n_plants: int) -> List[Object]:
        return [self._get_object(f"plant{i + 1}", self._Plant) for i in range(n_plants)]

    def _pump(self) -> Object:
        # The domain allows several pumps, but every default instance has exactly one.
        return self._get_object("pump1", self._Pump)

    def get_objects(self, params) -> List[Object]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        return (
            self._agents(params["n_agents"])
            + self._plants(params["n_plants"])
            + [self._pump()]
        )

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        _, agents_upper = hyperparam_range(instance_parameters_space["n_agents"])
        _, plants_upper = hyperparam_range(instance_parameters_space["n_plants"])
        return self._agents(agents_upper) + self._plants(plants_upper) + [self._pump()]

    def get_goal(self, params) -> List[FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")
        return [
            Equals(self._poured(plant), params["pour"])
            for plant in self._plants(params["n_plants"])
        ]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        params.check_valid_configuration()
        if not is_subspace(params.config_space, self.instance_parameter_space):
            raise ValueError(f"Invalid instance parameters: {params}")
        size = params["size"]
        pump = self._pump()
        res: dict[FNode, FNode] = {
            self._minx(): 1,
            self._maxx(): size,
            self._miny(): 1,
            self._maxy(): size,
            self._water_reserve(): params["pour"] * params["n_plants"],
            self._pump_closed(pump): TRUE(),
            self._free(pump): TRUE(),
            self._tap_x(pump): params["tap_x"],
            self._tap_y(pump): params["tap_y"],
        }
        agents = self._agents(params["n_agents"])
        for agent, (x, y) in zip(agents, agent_cells(params["n_agents"])):
            res[self._handfree(agent)] = TRUE()
            res[self._x(agent)] = x
            res[self._y(agent)] = y
        plants = self._plants(params["n_plants"])
        cells = plant_cells(size, params["n_agents"], params["n_plants"])
        for plant, (x, y) in zip(plants, cells):
            res[self._poured(plant)] = 0
            res[self._plant_x(plant)] = x
            res[self._plant_y(plant)] = y
        return res

    def check_instance_parameters(self, params: Configuration):
        size = params["size"]
        # The first two rules are also clauses of instance_parameter_space.
        # The agents start one per cell up the left column, so they must fit.
        if params["n_agents"] > size:
            return False
        # The pump must stand on the grid, where the agents can reach it.
        if params["tap_x"] > size or params["tap_y"] > size:
            return False
        # Each plant needs a border cell of its own, and the cells the agents
        # start on (all on the left column, so all on the border) are taken.
        if params["n_plants"] > 4 * (size - 1) - params["n_agents"]:
            return False
        return True
