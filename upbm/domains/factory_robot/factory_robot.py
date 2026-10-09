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
from typing import Any, Dict, List, Optional

from ConfigSpace import (
    ConfigurationSpace,
    Configuration,
    Integer,
    Categorical,
    Constant,
)
from unified_planning.io import PDDLReader
from unified_planning.model import Problem, Object, FNode
from unified_planning.shortcuts import TRUE, GE, LE

from upbm.generator import Generator
from upbm.utils import is_subspace, hyperparam_range

from .resources.ipc_factory_robot_data import IPC_INSTANCES, ROBOT_FLUENTS


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

CHARGING = "charging"
COOLING = "cooling"


def stations(n_stations: int) -> List[str]:
    """The station names, in the order the shipped instances declare them."""
    return [CHARGING, COOLING] + [f"assembly{i}" for i in range(n_stations - 2)]


class FactoryRobotGenerator(Generator):
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
            != FactoryRobotGenerator.get_domain_parameter_space()
        ):
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._Robot = self._domain.user_type("robot")
        self._Station = self._domain.user_type("station")
        self._at = self._domain.fluent("at")
        self._connected = self._domain.fluent("connected")
        self._has_charger = self._domain.fluent("has-charger")
        self._has_calibrator = self._domain.fluent("has-calibrator")
        self._free = self._domain.fluent("free")
        self._calibrated = self._domain.fluent("calibrated")
        self._workload = self._domain.fluent("workload")
        self._temperature = self._domain.fluent("temperature")
        self._production = self._domain.fluent("production")
        self._cooling_power = self._domain.fluent("cooling-power")
        self._robot_fluents = [self._domain.fluent(name) for name in ROBOT_FLUENTS]

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant != "ipc":
            raise ValueError(f"invalid variant {self.variant}")
        indices = sorted(IPC_INSTANCES)
        mapping["index"] = Integer(
            "index", (indices[0], indices[-1]), default=indices[0]
        )
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"FactoryRobot V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            return reader.parse_problem(
                str(RESOURCES_PATH / f"factory_robot_v{self.version}.pddl")
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

    def _robot(self, i: int) -> Object:
        return self._get_object(f"r{i}", self._Robot)

    def _station(self, name: str) -> Object:
        return self._get_object(name, self._Station)

    def _row(self, params: Configuration) -> Dict[str, Any]:
        return IPC_INSTANCES[params["index"]]

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        row = self._row(params)
        robots = [self._robot(i) for i in range(len(row["robots"]))]
        return robots + [self._station(s) for s in stations(row["n_stations"])]

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        first, last = hyperparam_range(instance_parameters_space["index"])
        rows = [IPC_INSTANCES[i] for i in IPC_INSTANCES if first <= i <= last]
        robots_upper = max(len(row["robots"]) for row in rows)
        stations_upper = max(row["n_stations"] for row in rows)
        return [self._robot(i) for i in range(robots_upper)] + [
            self._station(s) for s in stations(stations_upper)
        ]

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        row = self._row(params)
        # A workload target per robot, and a temperature bound on r0 alone.
        goals: List[FNode] = [
            GE(self._workload(self._robot(i)), target)
            for i, (_, target, *_) in enumerate(row["robots"])
        ]
        goals.append(LE(self._temperature(self._robot(0)), row["goal_temperature"]))
        return goals

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        row = self._row(params)
        places = stations(row["n_stations"])
        res: dict[FNode, FNode] = {}

        occupied = set()
        for i, (place, _, *values) in enumerate(row["robots"]):
            robot = self._robot(i)
            occupied.add(place)
            res[self._at(robot, self._station(place))] = TRUE()
            # every robot starts calibrated, idle and cold
            res[self._calibrated(robot)] = TRUE()
            res[self._workload(robot)] = 0
            res[self._temperature(robot)] = 0
            res[self._production(robot)] = 0
            for fluent, value in zip(self._robot_fluents, values):
                res[fluent(robot)] = value

        res[self._has_charger(self._station(CHARGING))] = TRUE()
        res[self._has_calibrator(self._station(COOLING))] = TRUE()
        for place in places:
            station = self._station(place)
            if place not in occupied:
                res[self._free(station)] = TRUE()
            res[self._cooling_power(station)] = (
                row["cooling_power"] if place == COOLING else 0
            )
        for a in places:
            for b in places:
                if a != b:
                    res[self._connected(self._station(a), self._station(b))] = TRUE()
        return res

    def check_instance_parameters(self, params: Configuration):
        return params["index"] in IPC_INSTANCES
