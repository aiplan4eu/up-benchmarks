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


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

# How many gears the generator can describe. The IPC set uses 2 to 5, and the
# per-gear tables below are only verified against those four gear counts, so
# the cap stays at the largest one the dataset shows.
MAX_GEARS = 5

# Fixed in every one of the 20 shipped instances, so these are not parameters.
MAX_ACCELERATION = 2
MIN_ACCELERATION = -1
ACC_STEP = 1

# The car always starts stopped at the origin, in first gear, with nothing
# used up yet.
START_DISTANCE = 0
START_SPEED = 0
START_ACCELERATION = 0

# The goal asks for a distance in [target, target + this]. It is 2 in every
# shipped instance.
GOAL_DISTANCE_TOLERANCE = 2

# Each gear covers a speed band two units wide, so the top speed follows from
# the number of gears: SPEED_PER_GEAR * n_gears, which is what every shipped
# instance has.
SPEED_PER_GEAR = 2


def gear_speed_band(gear: int) -> tuple[int, int]:
    """Return (gear_v_min, gear_v_max) of a gear. Gears are 1-indexed."""
    return (SPEED_PER_GEAR * (gear - 1), SPEED_PER_GEAR * gear)


def gear_max_acceleration(gear: int, n_gears: int) -> int:
    """Return the acceleration ceiling of a gear.

    First gear pulls hardest and the top gear cannot accelerate at all, which
    is what forces the car to shift up to go fast and back down to stop.
    """
    if gear == 1:
        return 2
    if gear == n_gears:
        return 0
    return 1


def gear_fuel_aligned(gear: int) -> int:
    """Fuel burnt per step when the speed is inside the gear's band.

    The shipped values are 11, 9, 8, 7, 6 for gears 1 to 5: higher gears are
    more efficient, and first gear is a step worse than the trend.
    """
    return 11 if gear == 1 else 11 - gear


def gear_fuel_under(gear: int) -> int:
    """Fuel burnt per step when the speed is below the gear's band."""
    return 18 if gear == 1 else 17


def gear_fuel_over(gear: int, n_gears: int) -> int:
    """Fuel burnt per step when the speed is above the gear's band.

    This is the one table that depends on how many gears the car has: with
    more gears every over-revving step is penalised more. Verified against all
    four gear counts of the IPC set (2, 3, 4 and 5 gears).
    """
    if gear == 1:
        return 15 + n_gears
    return 16 + n_gears - 2 * gear


class GearCarGenerator(Generator):
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
        self._gear_v_min = self._domain.fluent("gear_v_min")
        self._gear_v_max = self._domain.fluent("gear_v_max")
        self._gear_min_acceleration = self._domain.fluent("gear_min_acceleration")
        self._gear_max_acceleration = self._domain.fluent("gear_max_acceleration")
        self._gear_fuel_aligned = self._domain.fluent("gear_fuel_aligned")
        self._gear_fuel_under = self._domain.fluent("gear_fuel_under")
        self._gear_fuel_over = self._domain.fluent("gear_fuel_over")

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant != "ipc":
            raise ValueError(f"invalid variant {self.variant}")
        # The IPC set uses 2, 3, 4 and 5 gears; a car needs at least two gears
        # for gear_up and gear_down to exist at all.
        mapping["n_gears"] = Integer("n_gears", (2, MAX_GEARS), default=2)
        # The distance to cover, the (>= (d) X) half of the goal.
        mapping["target_distance"] = Integer(
            "target_distance", (1, MAX_INT), default=260
        )
        mapping["fuel"] = Integer("fuel", (0, MAX_INT), default=406)
        # alpha is the per-step time price and beta the per-unit-fuel price in
        # (:metric minimize (cost)), where a drive step costs
        # alpha + beta * gear_fuel_*. In 19 of the 20 shipped instances
        # alpha = beta * (fuel + 1), which makes alpha a big-M: any saving in
        # elapsed time beats any saving in fuel. The 20th (p000) breaks that
        # relation - it is a warm-up copied from p01, keeping p01's alpha and
        # beta while its fuel was lowered - so alpha cannot be derived and has
        # to be stated. The defaults here are p01's.
        mapping["alpha"] = Integer("alpha", (0, MAX_INT), default=19536)
        mapping["beta"] = Integer("beta", (0, MAX_INT), default=48)
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
            # Every shipped instance minimises (cost), which sums a big-M price
            # per step and a price per unit of fuel, so the metric belongs to
            # the domain rather than to a single instance. Problem.clone()
            # copies it into every instance.
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

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        return [self._gear(i + 1) for i in range(params["n_gears"])]

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        _, gears_upper = hyperparam_range(instance_parameters_space["n_gears"])
        return [self._gear(i + 1) for i in range(gears_upper)]

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        target = params["target_distance"]
        # The car has to stop inside a short window past the target, back in
        # first gear, and it has to have driven at all (fuel_used > 0).
        return [
            GE(self._d(), target),
            LE(self._d(), target + GOAL_DISTANCE_TOLERANCE),
            self._current_gear(self._gear(1)),
            Equals(self._v(), 0),
            Equals(self._a(), 0),
            GE(self._fuel(), 0),
            GT(self._fuel_used(), 0),
        ]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        n_gears = params["n_gears"]
        res: dict[FNode, FNode] = {
            self._current_gear(self._gear(1)): TRUE(),
            self._d(): START_DISTANCE,
            self._v(): START_SPEED,
            self._a(): START_ACCELERATION,
            self._max_acceleration(): MAX_ACCELERATION,
            self._min_acceleration(): MIN_ACCELERATION,
            self._max_speed(): SPEED_PER_GEAR * n_gears,
            self._acc_step(): ACC_STEP,
            self._fuel(): params["fuel"],
            self._fuel_used(): 0,
            self._elapsed_time(): 0,
            self._cost(): 0,
            self._alpha(): params["alpha"],
            self._beta(): params["beta"],
            self._shift_count(): 0,
        }
        for i in range(1, n_gears + 1):
            gear = self._gear(i)
            v_min, v_max = gear_speed_band(i)
            res[self._gear_v_min(gear)] = v_min
            res[self._gear_v_max(gear)] = v_max
            res[self._gear_min_acceleration(gear)] = MIN_ACCELERATION
            res[self._gear_max_acceleration(gear)] = gear_max_acceleration(i, n_gears)
            res[self._gear_fuel_aligned(gear)] = gear_fuel_aligned(i)
            res[self._gear_fuel_under(gear)] = gear_fuel_under(i)
            res[self._gear_fuel_over(gear)] = gear_fuel_over(i, n_gears)
            if i < n_gears:
                res[self._gear_next(gear, self._gear(i + 1))] = TRUE()
        # `current_gear` of the other gears defaults to false, and the shipped
        # instances do not list those either.
        return res

    def check_instance_parameters(self, params: Configuration):
        # NOTE this is a necessary condition, not a full solvability check: it
        # only rejects instances whose fuel provably cannot cover the distance.
        # A drive step adds (2v + a) to the distance, and the drive actions
        # require both v <= max_speed and v + a <= max_speed, so a step can add
        # at most 2 * max_speed. The cheapest step is the top gear driven
        # inside its band. Whether the car can also stop exactly inside the
        # goal window is left to the planner, in the same spirit as the
        # expedition port.
        n_gears = params["n_gears"]
        cheapest_step = gear_fuel_aligned(n_gears)
        assert cheapest_step > 0, "the fuel tables stop making sense past MAX_GEARS"
        longest_step = 2 * SPEED_PER_GEAR * n_gears
        reachable = (params["fuel"] // cheapest_step) * longest_step
        return reachable >= params["target_distance"]
