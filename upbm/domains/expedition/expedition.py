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
from typing import Any, List, Optional

from ConfigSpace import (
    ConfigurationSpace,
    Configuration,
    Integer,
    Categorical,
    Constant,
)
from unified_planning.io import PDDLReader
from unified_planning.model import Problem, Object, FNode
from unified_planning.shortcuts import TRUE

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

# Every shipped instance agrees on all of these, so they are fixed here rather
# than exposed as parameters.
N_SLEDS = 2
SLED_CAPACITY = 4
SLED_INITIAL_SUPPLIES = 1
# The first waypoint of every chain is a depot holding this much; every other
# waypoint starts empty.
DEPOT_SUPPLIES = 1000

# The IPC set uses at most two chains, named with the prefixes below: waypoints
# are wa0, wa1, ... on the first chain and wb0, wb1, ... on the second.
CHAIN_PREFIXES = ["wa", "wb"]


class ExpeditionGenerator(Generator):
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
            != ExpeditionGenerator.get_domain_parameter_space()
        ):
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._Sled = self._domain.user_type("sled")
        self._Waypoint = self._domain.user_type("waypoint")
        self._at = self._domain.fluent("at")
        self._is_next = self._domain.fluent("is_next")
        self._sled_supplies = self._domain.fluent("sled_supplies")
        self._sled_capacity = self._domain.fluent("sled_capacity")
        self._waypoint_supplies = self._domain.fluent("waypoint_supplies")

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant != "ipc":
            raise ValueError(f"invalid variant {self.variant}")
        # The IPC set uses chains of 6 to 15 waypoints; the default reproduces
        # the shortest one. A chain needs at least two waypoints for the sleds
        # to have somewhere to go.
        mapping["n_waypoints"] = Integer("n_waypoints", (2, MAX_INT), default=6)
        # The set comes in two halves: ten instances where both sleds share one
        # chain, and ten where each sled gets a chain of its own.
        mapping["n_chains"] = Integer("n_chains", (1, len(CHAIN_PREFIXES)), default=1)
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"Expedition V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            # The shipped instances define no :metric, so no quality metric is
            # attached to the skeleton either.
            return reader.parse_problem(
                str(RESOURCES_PATH / f"expedition_v{self.version}.pddl")
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

    def _sled(self, i: int) -> Object:
        return self._get_object(f"s{i}", self._Sled)

    def _waypoint(self, chain: int, i: int) -> Object:
        return self._get_object(f"{CHAIN_PREFIXES[chain]}{i}", self._Waypoint)

    def _chain_of(self, sled_index: int, n_chains: int) -> int:
        """Which chain a sled starts on.

        With one chain both sleds share it, with two they get one each, which
        is exactly what the two halves of the IPC set do.
        """
        return sled_index % n_chains

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        objs: List[Object] = [self._sled(i) for i in range(N_SLEDS)]
        for chain in range(params["n_chains"]):
            for i in range(params["n_waypoints"]):
                objs.append(self._waypoint(chain, i))
        return objs

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        _, waypoints_upper = hyperparam_range(instance_parameters_space["n_waypoints"])
        _, chains_upper = hyperparam_range(instance_parameters_space["n_chains"])
        objs: List[Object] = [self._sled(i) for i in range(N_SLEDS)]
        for chain in range(chains_upper):
            for i in range(waypoints_upper):
                objs.append(self._waypoint(chain, i))
        return objs

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        # every sled has to reach the far end of the chain it started on
        last = params["n_waypoints"] - 1
        return [
            self._at(
                self._sled(i),
                self._waypoint(self._chain_of(i, params["n_chains"]), last),
            )
            for i in range(N_SLEDS)
        ]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        n_chains = params["n_chains"]
        n_waypoints = params["n_waypoints"]
        res: dict[FNode, FNode] = {}
        for chain in range(n_chains):
            for i in range(n_waypoints):
                waypoint = self._waypoint(chain, i)
                # only the start of a chain is a depot, the rest starts empty
                res[self._waypoint_supplies(waypoint)] = DEPOT_SUPPLIES if i == 0 else 0
                if i + 1 < n_waypoints:
                    res[self._is_next(waypoint, self._waypoint(chain, i + 1))] = TRUE()
        for i in range(N_SLEDS):
            sled = self._sled(i)
            res[self._at(sled, self._waypoint(self._chain_of(i, n_chains), 0))] = TRUE()
            res[self._sled_capacity(sled)] = SLED_CAPACITY
            res[self._sled_supplies(sled)] = SLED_INITIAL_SUPPLIES
        # `at` and `is_next` both default to false, so the pairs that are not
        # listed here are false, exactly as in the shipped instances.
        return res

    def check_instance_parameters(self, params: Configuration):
        # NOTE no real solvability check is done here. Reaching the end of a
        # chain is a supply ferrying problem: a sled carries at most
        # SLED_CAPACITY and burns one supply per move, so it has to shuttle
        # supplies forward and cache them along the way, and the cost of that
        # grows quickly with the length of the chain. With a depot of
        # DEPOT_SUPPLIES a long enough chain stops being solvable, but working
        # out exactly where that happens is itself a hard problem, so nothing
        # is rejected here. The shipped instances (chains of 6 to 15) all sit
        # inside the solvable range.
        return True
