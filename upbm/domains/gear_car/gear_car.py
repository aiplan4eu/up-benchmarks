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
from unified_planning.model.metrics import MinimizeExpressionOnFinalState
from unified_planning.shortcuts import TRUE, Equals, GE, GT, LE

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range

from .resources.ipc_gear_car_data import GEAR_FIELDS, IPC_CARS, IPC_INSTANCES


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"


def generic_car(n_gears: int) -> dict[str, Any]:
    """The car of the generic variant, in the same shape as an IPC_CARS entry.

    Every value is the smallest whole number that keeps the gearbox's shape:
    first gear pulls hardest, the top gear only cruises, and the higher the
    gear the less fuel a step inside its speed band burns. A step outside the
    band burns more than any step inside one. First gear alone can drive any
    plan, so saving fuel is the only reason to shift.
    """
    gears = []
    for gear in range(1, n_gears + 1):
        if gear == 1:
            max_acceleration = 2
        elif gear == n_gears:
            max_acceleration = 0
        else:
            max_acceleration = 1
        # in the order of GEAR_FIELDS
        gears.append(
            (
                # speed band, as wide as first gear's strongest push
                2 * (gear - 1),
                2 * gear,
                -1,  # every gear can brake
                max_acceleration,
                n_gears + 1 - gear,  # fuel inside the band: 1 in the top gear
                n_gears + 1,  # below the band
                n_gears + 1,  # above the band
            )
        )
    return {
        "max_acceleration": 2,
        "min_acceleration": -1,
        "acc_step": 1,
        "max_speed": 2 * n_gears,
        "gears": gears,
    }


class GearCarGenerator(Generator):
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
        if domain_params.config_space != GearCarGenerator.get_domain_parameter_space():
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._Gear = self._domain.user_type("gear")
        self._current_gear = self._domain.fluent("current_gear")
        self._gear_next = self._domain.fluent("gear_next")
        self._d = self._domain.fluent("d")
        self._v = self._domain.fluent("v")
        self._a = self._domain.fluent("a")
        self._max_acceleration = self._domain.fluent("max_acceleration")
        self._min_acceleration = self._domain.fluent("min_acceleration")
        self._max_speed = self._domain.fluent("max_speed")
        self._acc_step = self._domain.fluent("acc_step")
        self._fuel = self._domain.fluent("fuel")
        self._fuel_used = self._domain.fluent("fuel_used")
        self._elapsed_time = self._domain.fluent("elapsed_time")
        self._cost = self._domain.fluent("cost")
        self._alpha = self._domain.fluent("alpha")
        self._beta = self._domain.fluent("beta")
        self._shift_count = self._domain.fluent("shift_count")
        self._gear_fluents = [self._domain.fluent(name) for name in GEAR_FIELDS]

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant == "ipc":
            indices = sorted(IPC_INSTANCES)
            mapping["index"] = Integer(
                "index", (indices[0], indices[-1]), default=indices[0]
            )
            return ConfigurationSpace(name=mapping)
        if self.variant != "generic":
            raise ValueError(f"invalid variant {self.variant}")
        mapping["n_gears"] = Integer("n_gears", (2, MAX_INT), default=3)
        mapping["target_distance"] = Integer(
            "target_distance", (1, MAX_INT), default=100
        )
        mapping["fuel"] = Integer("fuel", (0, MAX_INT), default=30)
        # The price of one unit of fuel in (:metric minimize (cost)). Every
        # gear shift adds 1 to cost, so beta is how many shifts a unit of fuel
        # is worth. At least 1, or the metric would not count fuel or time at
        # all (alpha, the price of a step, is derived from it).
        mapping["beta"] = Integer("beta", (1, MAX_INT), default=1)
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"GearCar V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            domain = reader.parse_problem(
                str(RESOURCES_PATH / f"gear_car_v{self.version}.pddl")
            )
            domain.add_quality_metric(
                MinimizeExpressionOnFinalState(domain.fluent("cost")())
            )
            return domain
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

    def _gear(self, gear: int) -> Object:
        """The object of a gear. Gears are 1-indexed, like the dataset's g1."""
        return self._get_object(f"g{gear}", self._Gear)

    def _instance_data(self, params: Configuration) -> dict[str, Any]:
        """Everything an instance is built from, in the same shape for both
        variants: n_gears, the goal window distance_min/distance_max, fuel,
        alpha, beta, and the car (an IPC_CARS entry, or generic_car's).
        """
        if self.variant == "ipc":
            row = IPC_INSTANCES[params["index"]]
            return {**row, "car": IPC_CARS[row["n_gears"]]}
        n_gears = params["n_gears"]
        target = params["target_distance"]
        fuel = params["fuel"]
        beta = params["beta"]
        return {
            "n_gears": n_gears,
            # A plan that starts and ends stopped always covers an even
            # distance, so a window of 1 keeps an odd target reachable.
            "distance_min": target,
            "distance_max": target + 1,
            "fuel": fuel,
            # A drive step costs alpha plus beta per unit of fuel it burns.
            # This alpha is worth more than all the fuel, so one step fewer
            # always beats any fuel saving: plans rank by time, then fuel.
            "alpha": beta * (fuel + 1),
            "beta": beta,
            "car": generic_car(n_gears),
        }

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        n_gears = self._instance_data(params)["n_gears"]
        return [self._gear(i + 1) for i in range(n_gears)]

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        if self.variant == "ipc":
            first, last = hyperparam_range(instance_parameters_space["index"])
            gears_upper = max(
                IPC_INSTANCES[i]["n_gears"] for i in IPC_INSTANCES if first <= i <= last
            )
        else:
            _, gears_upper = hyperparam_range(instance_parameters_space["n_gears"])
        return [self._gear(i + 1) for i in range(gears_upper)]

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        data = self._instance_data(params)
        return [
            GE(self._d(), data["distance_min"]),
            LE(self._d(), data["distance_max"]),
            self._current_gear(self._gear(1)),
            Equals(self._v(), 0),
            Equals(self._a(), 0),
            GE(self._fuel(), 0),
            GT(self._fuel_used(), 0),
        ]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        data = self._instance_data(params)
        car = data["car"]
        n_gears = data["n_gears"]
        res: dict[FNode, FNode] = {
            self._current_gear(self._gear(1)): TRUE(),
            self._d(): 0,
            self._v(): 0,
            self._a(): 0,
            self._max_acceleration(): car["max_acceleration"],
            self._min_acceleration(): car["min_acceleration"],
            self._max_speed(): car["max_speed"],
            self._acc_step(): car["acc_step"],
            self._fuel(): data["fuel"],
            self._fuel_used(): 0,
            self._elapsed_time(): 0,
            self._cost(): 0,
            self._alpha(): data["alpha"],
            self._beta(): data["beta"],
            self._shift_count(): 0,
        }
        for i, row in enumerate(car["gears"], start=1):
            gear = self._gear(i)
            for fluent, value in zip(self._gear_fluents, row):
                res[fluent(gear)] = value
            if i < n_gears:
                res[self._gear_next(gear, self._gear(i + 1))] = TRUE()
        return res

    def check_instance_parameters(self, params: Configuration):
        if self.variant == "ipc":
            return params["index"] in IPC_INSTANCES
        # Every generic configuration is accepted, so an instance may not have
        # the fuel to finish.
        return True
