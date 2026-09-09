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

import random
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

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
from upbm.utils import MAX_INT, is_subspace, hyperparam_range


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

# The two special stations. Every instance has exactly one of each, and the
# rest are general-purpose assembly stations.
CHARGING = "charging"
COOLING = "cooling"

# Every robot starts idle, cool and calibrated in all 20 shipped instances.
START_WORKLOAD = 0
START_TEMPERATURE = 0
START_PRODUCTION = 0

# Only the cooling station cools; every other station has cooling-power 0.
NO_COOLING = 0

# The draw pools of the original generate.py, recovered from the dataset.
CAPACITY_CHOICES = [80, 100, 120, 150]
WORK_COST_CHOICES = [8, 10, 12, 15]
EFFICIENCY_CHOICES = [2, 3, 4]
MAX_TEMP_SPREAD = 5  # max-temp is the argument plus 0..5
COOLING_POWER_RANGE = (4, 6)
ENERGY_DEFICIT = 20  # energy is capacity minus 0..20
WORKLOAD_SPREAD = 2  # the goal is the argument plus -2..2

# The seed the IPC set was generated with. Every one of the 20 instances
# records `--seed 42` in its header.
IPC_SEED = 42


class RobotData(NamedTuple):
    """The per-instance values the original generator drew at random."""

    capacity: List[int]
    work_cost: List[int]
    max_temp: List[int]
    efficiency: List[int]
    cooling_power: int
    at: List[str]
    energy: List[int]
    workload_goal: List[int]


def stations(n_stations: int) -> List[str]:
    """The station names, in the order the shipped instances declare them."""
    return [CHARGING, COOLING] + [f"assembly{i}" for i in range(n_stations - 2)]


def draw(
    n_robots: int, n_stations: int, workload: int, max_temp: int, seed: int
) -> RobotData:
    """Reproduce the random data of one instance.

    This is the original `generate.py` reconstructed from the dataset: every
    shipped instance records the exact call that made it
    (`python generate.py --robots N --stations N --workload N --max-temp N
    --seed 42`), but not the script, so the call sequence below was recovered
    by matching candidate draws against all 20 instances at once. It
    reproduces every one of them exactly, field for field.

    Three properties of the set made that possible: the seed is 42 in all 20,
    so there is a single stream; the instances come in pairs that share
    `--robots`/`--stations` and differ only in the other two arguments, and
    every drawn value is identical within a pair, which shows the draws depend
    on nothing but the robot count and the seed; and `capacity` is a stable
    prefix as the robot count grows while every other field shifts, which is
    what a generator drawing field-by-field (rather than robot-by-robot) looks
    like, and pins `capacity` as the first pass.

    The order of the passes matters, and so do two details that look
    interchangeable but are not: the positions come from shuffling the station
    list and taking a prefix, not from `sample()`, and the energy is the
    capacity minus a draw rather than a draw from a shifted range. Either
    substitution still produces plausible numbers, but consumes the stream
    differently and stops reproducing the dataset.
    """
    rng = random.Random(seed)
    capacity = [rng.choice(CAPACITY_CHOICES) for _ in range(n_robots)]
    work_cost = [rng.choice(WORK_COST_CHOICES) for _ in range(n_robots)]
    max_temps = [max_temp + rng.randint(0, MAX_TEMP_SPREAD) for _ in range(n_robots)]
    efficiency = [rng.choice(EFFICIENCY_CHOICES) for _ in range(n_robots)]
    # one draw for the cooling station, not one per robot
    cooling_power = rng.randint(*COOLING_POWER_RANGE)
    places = stations(n_stations)
    rng.shuffle(places)
    at = places[:n_robots]
    energy = [c - rng.randint(0, ENERGY_DEFICIT) for c in capacity]
    workload_goal = [
        workload + rng.randint(-WORKLOAD_SPREAD, WORKLOAD_SPREAD)
        for _ in range(n_robots)
    ]
    return RobotData(
        capacity=capacity,
        work_cost=work_cost,
        max_temp=max_temps,
        efficiency=efficiency,
        cooling_power=cooling_power,
        at=at,
        energy=energy,
        workload_goal=workload_goal,
    )


class FactoryRobotGenerator(Generator):
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
        self._energy = self._domain.fluent("energy")
        self._workload = self._domain.fluent("workload")
        self._temperature = self._domain.fluent("temperature")
        self._production = self._domain.fluent("production")
        self._capacity = self._domain.fluent("capacity")
        self._work_cost = self._domain.fluent("work-cost")
        self._max_temp = self._domain.fluent("max-temp")
        self._efficiency = self._domain.fluent("efficiency")
        self._cooling_power = self._domain.fluent("cooling-power")

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant != "ipc":
            raise ValueError(f"invalid variant {self.variant}")
        # These are the four arguments of the original generate.py, which
        # every shipped instance records in its header. The IPC set uses 2 to
        # 12 robots with n_robots + 3 stations (n_robots + 2 for the largest).
        mapping["n_robots"] = Integer("n_robots", (1, MAX_INT), default=2)
        # At least a charging and a cooling station, and one more than there
        # are robots so that somebody can always move; see
        # check_instance_parameters.
        mapping["n_stations"] = Integer("n_stations", (2, MAX_INT), default=5)
        # The workload each robot must reach, give or take 2.
        mapping["workload"] = Integer("workload", (0, MAX_INT), default=40)
        # The temperature ceiling: the goal bound, and the base of each
        # robot's own max-temp.
        mapping["max_temp"] = Integer("max_temp", (0, MAX_INT), default=20)
        # The generator's own --seed. It is 42 in all 20 shipped instances, so
        # the default reproduces the IPC set; changing it draws a different
        # factory of the same shape.
        mapping["seed"] = Integer("seed", (0, MAX_INT), default=IPC_SEED)
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

    def _draw(self, params: Configuration) -> RobotData:
        return draw(
            params["n_robots"],
            params["n_stations"],
            params["workload"],
            params["max_temp"],
            params["seed"],
        )

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        robots = [self._robot(i) for i in range(params["n_robots"])]
        return robots + [self._station(s) for s in stations(params["n_stations"])]

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        _, robots_upper = hyperparam_range(instance_parameters_space["n_robots"])
        _, stations_upper = hyperparam_range(instance_parameters_space["n_stations"])
        return [self._robot(i) for i in range(robots_upper)] + [
            self._station(s) for s in stations(stations_upper)
        ]

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        data = self._draw(params)
        # Each robot has to reach its own workload target, and the first robot
        # additionally has to stay below the temperature ceiling. Every
        # shipped instance has exactly this shape - one temperature bound, on
        # r0 only, at the max_temp argument rather than the robot's own drawn
        # max-temp.
        goals: List[FNode] = [
            GE(self._workload(self._robot(i)), target)
            for i, target in enumerate(data.workload_goal)
        ]
        goals.append(LE(self._temperature(self._robot(0)), params["max_temp"]))
        return goals

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        n_robots = params["n_robots"]
        places = stations(params["n_stations"])
        data = self._draw(params)
        res: dict[FNode, FNode] = {}

        for i in range(n_robots):
            robot = self._robot(i)
            res[self._at(robot, self._station(data.at[i]))] = TRUE()
            res[self._calibrated(robot)] = TRUE()
            res[self._energy(robot)] = data.energy[i]
            res[self._workload(robot)] = START_WORKLOAD
            res[self._temperature(robot)] = START_TEMPERATURE
            res[self._production(robot)] = START_PRODUCTION
            res[self._capacity(robot)] = data.capacity[i]
            res[self._work_cost(robot)] = data.work_cost[i]
            res[self._max_temp(robot)] = data.max_temp[i]
            res[self._efficiency(robot)] = data.efficiency[i]

        res[self._has_charger(self._station(CHARGING))] = TRUE()
        res[self._has_calibrator(self._station(COOLING))] = TRUE()
        # Every station nobody is standing on is free, the two special ones
        # included.
        occupied = set(data.at)
        for place in places:
            station = self._station(place)
            if place not in occupied:
                res[self._free(station)] = TRUE()
            res[self._cooling_power(station)] = (
                data.cooling_power if place == COOLING else NO_COOLING
            )
        # The stations form a full clique, both directions, no self loops.
        for a in places:
            for b in places:
                if a != b:
                    res[self._connected(self._station(a), self._station(b))] = TRUE()
        return res

    def check_instance_parameters(self, params: Configuration):
        # NOTE this is a necessary condition, not a full solvability check, in
        # the same spirit as the expedition and gear-car ports.
        #
        # Every robot stands on its own station, and there has to be one to
        # spare. That is not a nicety: `move` requires the target station to
        # be free, so with exactly as many stations as robots nobody can ever
        # move, and a robot that did not start on the charging station can
        # never recharge. With one spare, the clique means any robot can
        # always reach the charger and the cooler, so it can alternate
        # working, recharging and cooling indefinitely - and since workload
        # only ever increases, any target is then reachable given enough
        # steps.
        #
        # The charging and cooling stations are guaranteed by the parameter
        # space, whose lower bound for n_stations is 2.
        return params["n_stations"] > params["n_robots"]
