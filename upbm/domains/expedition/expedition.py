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

# The first waypoint of every chain is a depot holding this much; every other
# waypoint starts empty. NOTE 1000 is meant as "effectively unlimited" and is
# enough for anything near the size of the original IPC instances, but it is not
# infinite: a long enough chain, or a small enough sled capacity, needs more
# than this to be crossable at all. Make it a parameter if that ever bites.
DEPOT_SUPPLIES = 1000


def chain_prefix(chain: int) -> str:
    """The waypoint name prefix of a chain: wa, wb, ... wz, waa, wab, ...

    The IPC set only ever uses the first two, and those keep the shipped names
    wa and wb; the rest carry on with the same spreadsheet-column scheme so
    that any number of chains has a name.
    """
    letters = ""
    n = chain
    while n >= 0:
        letters = chr(ord("a") + n % 26) + letters
        n = n // 26 - 1
    return f"w{letters}"


class ExpeditionGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
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
        mapping["n_waypoints"] = Integer("n_waypoints", (2, MAX_INT), default=6)
        mapping["n_chains"] = Integer("n_chains", (1, MAX_INT), default=1)
        mapping["n_sleds"] = Integer("n_sleds", (1, MAX_INT), default=2)
        # sled capacity 3 is necessary to allow bringing supplies up the chain
        mapping["sled_capacity"] = Integer("sled_capacity", (4, MAX_INT), default=3)
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
        return self._get_object(f"{chain_prefix(chain)}{i}", self._Waypoint)

    def _chain_of(self, sled_index: int, n_chains: int) -> int:
        """Which chain a sled starts on.

        Round robin: with one chain the sleds all share it, with as many chains
        as sleds they get one each, which is exactly what the two halves of the
        IPC set do. In between, the sleds spread as evenly as they can.
        """
        return sled_index % n_chains

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        objs: List[Object] = [self._sled(i) for i in range(params["n_sleds"])]
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
        _, sleds_upper = hyperparam_range(instance_parameters_space["n_sleds"])
        objs: List[Object] = [self._sled(i) for i in range(sleds_upper)]
        for chain in range(chains_upper):
            for i in range(waypoints_upper):
                objs.append(self._waypoint(chain, i))
        return objs

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        last = params["n_waypoints"] - 1
        return [
            self._at(
                self._sled(i),
                self._waypoint(self._chain_of(i, params["n_chains"]), last),
            )
            for i in range(params["n_sleds"])
        ]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        n_chains = params["n_chains"]
        n_waypoints = params["n_waypoints"]
        res: dict[FNode, FNode] = {}
        for chain in range(n_chains):
            for i in range(n_waypoints):
                waypoint = self._waypoint(chain, i)
                res[self._waypoint_supplies(waypoint)] = DEPOT_SUPPLIES if i == 0 else 0
                if i + 1 < n_waypoints:
                    res[self._is_next(waypoint, self._waypoint(chain, i + 1))] = TRUE()
        for i in range(params["n_sleds"]):
            sled = self._sled(i)
            res[self._at(sled, self._waypoint(self._chain_of(i, n_chains), 0))] = TRUE()
            res[self._sled_capacity(sled)] = params["sled_capacity"]
            res[self._sled_supplies(sled)] = 1
        return res

    def check_instance_parameters(self, params: Configuration):
        # NOTE no real solvability check is done here. Reaching the end of a
        # chain is a supply ferrying problem: a sled carries at most
        # sled_capacity and burns one supply per move, so it has to shuttle
        # supplies forward and cache them along the way, and the cost of that
        # grows quickly with the length of the chain. With a depot of
        # DEPOT_SUPPLIES a long enough chain stops being solvable, but working
        # out exactly where that happens is itself a hard problem, so nothing
        # is rejected here.
        return True
