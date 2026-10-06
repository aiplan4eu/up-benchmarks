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


# The car of the "generic" variant. The "ipc" variant reads its cars from
# resources/ipc_gear_car_data.py instead, so nothing from here down to
# GearCarGenerator applies to it.
#
# Every value is the smallest whole number that gives the gearbox the shape
# described next to it.

# Accelerations change in steps of this size. It is the unit: the other
# accelerations below are counted in steps.
ACC_STEP = 1
# Every gear brakes by one step, the least that lets a moving car slow down.
GEAR_MIN_ACCELERATION = -ACC_STEP
# First gear, the one the car sets off in, pulls one step harder than the gears
# above it, as the lowest gear of a real gearbox does.
FIRST_GEAR_MAX_ACCELERATION = 2 * ACC_STEP
# Each gear covers a band of speeds as wide as first gear can add in one drive
# step, so a car setting off at full throttle is still inside first gear's band
# after its first step. max_speed is SPEED_PER_GEAR * n_gears.
SPEED_PER_GEAR = FIRST_GEAR_MAX_ACCELERATION
# The goal asks for a distance in [target, target + GOAL_DISTANCE_TOLERANCE].
# A drive step adds (2v + a), and a plan that starts and ends stopped has its
# accelerations sum to zero, so the distance reached is ALWAYS EVEN, whatever
# the gearbox. 1 is the smallest window that keeps an odd target reachable;
# against an even target it changes nothing, since the window then holds only
# one even distance.
GOAL_DISTANCE_TOLERANCE = 1


def gear_speed_band(gear: int) -> tuple[int, int]:
    """Return (gear_v_min, gear_v_max) of a generic gear. Gears are 1-indexed.

    The bands tile [0, max_speed] and share their endpoints, so at the speed
    where one gear ends and the next begins either of the two is "aligned".
    """
    return (SPEED_PER_GEAR * (gear - 1), SPEED_PER_GEAR * gear)


def gear_max_acceleration(gear: int, n_gears: int) -> int:
    """Return the acceleration ceiling of a generic gear.

    First gear pulls hardest (FIRST_GEAR_MAX_ACCELERATION). Every gear between
    the first and the top gets one step, the least that lets it accelerate at
    all. The top gear only cruises: it can hold or shed speed but not add any,
    so the speed the car travels at has to be built up in the gears below it.

    Note the top gear's 0 does *not* force the car to shift back down to stop:
    GEAR_MIN_ACCELERATION applies in the top gear too, so it can brake there.
    What forces the downshift is the goal asking for first gear.
    """
    if gear == 1:
        return FIRST_GEAR_MAX_ACCELERATION
    if gear == n_gears:
        return 0
    return ACC_STEP


# The fuel tables. Each drive step burns fuel according to whether the speed is
# inside the current gear's band ("aligned"), below it or above it.
#
# They are the whole reason to shift. First gear's acceleration range contains
# every other gear's, and the speed bands only choose which table a drive step
# pays from, so a car that never leaves first gear can drive anything the other
# gears can. What it cannot do is drive cheaply: the tables make the higher
# gears cheaper inside their bands, and every gear dearer outside its band than
# any gear inside one.


def gear_fuel_aligned(gear: int, n_gears: int) -> int:
    """Fuel a generic gear burns per step when the speed is inside its band.

    The top gear burns 1, the unit of fuel, and each gear below it burns one
    unit more: the higher the gear, the cheaper the step, which is the saving
    shifting up buys.
    """
    return n_gears + 1 - gear


def gear_fuel_outside(n_gears: int) -> int:
    """Fuel a generic gear burns per step when the speed is outside its band.

    One unit more than the dearest step inside a band (first gear's), so
    driving in the wrong gear always costs more than driving in any right one.
    Below the band it punishes shifting up too early, above it staying in a low
    gear at speed. The domain keeps the two cases in separate tables; here they
    share this one value.

    First gear's "below" entry and the top gear's "above" entry are never used:
    no drive action lets the speed go below 0, where first gear's band starts,
    or above max_speed, where the top gear's band ends.
    """
    return n_gears + 1


def generic_car(n_gears: int) -> dict[str, Any]:
    """The car of the generic variant, in the same shape as an IPC_CARS entry."""
    gears = []
    for gear in range(1, n_gears + 1):
        v_min, v_max = gear_speed_band(gear)
        outside = gear_fuel_outside(n_gears)
        # in the order of GEAR_FIELDS
        gears.append(
            (
                v_min,
                v_max,
                GEAR_MIN_ACCELERATION,
                gear_max_acceleration(gear, n_gears),
                gear_fuel_aligned(gear, n_gears),
                outside,
                outside,
            )
        )
    return {
        # Every action also checks car-wide acceleration limits beside the
        # gear's own. They are the extremes of the gears' limits, so it is
        # always the gear's own limits that apply.
        "max_acceleration": FIRST_GEAR_MAX_ACCELERATION,
        "min_acceleration": GEAR_MIN_ACCELERATION,
        "acc_step": ACC_STEP,
        "max_speed": SPEED_PER_GEAR * n_gears,
        "gears": gears,
    }


def generic_alpha(fuel: int, beta: int) -> int:
    """The per-step price alpha of (:metric minimize (cost)), generic variant.

    A drive step adds alpha + beta * (the fuel it burns) to cost. alpha is one
    beta more than all the fuel the car carries is worth, and a plan can never
    burn more fuel than it starts with, so one drive step fewer always beats
    any saving in fuel: the metric ranks plans by time first and fuel second.
    """
    return beta * (fuel + 1)


class GearCarGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        # "generic" builds its car from the rules at the top of this file;
        # "ipc" rebuilds the 20 shipped instances from
        # resources/ipc_gear_car_data.py.
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
        # the per-gear fluents, in the order a car's gear rows store them
        self._gear_fluents = [self._domain.fluent(name) for name in GEAR_FIELDS]

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant == "ipc":
            # Which shipped instance: the number in its file name, p000 -> 0,
            # p01 -> 1 ... p19 -> 19.
            indices = sorted(IPC_INSTANCES)
            mapping["index"] = Integer(
                "index", (indices[0], indices[-1]), default=indices[0]
            )
            return ConfigurationSpace(name=mapping)
        if self.variant != "generic":
            raise ValueError(f"invalid variant {self.variant}")
        # The defaults make a car that can only finish by shifting: covering
        # 100 with 3 gears takes at least 23 units of fuel if it shifts and 48
        # if it stays in first gear, and it carries 30. The slack over 23 lets
        # the metric trade fuel for time: the cheapest plan in fuel takes 14
        # drive steps, the best one under the metric 13, burning 24.
        #
        # How many gears the car has. Two is the fewest that makes
        # gear_up/gear_down exist at all, and there is no upper bound because
        # every rule of the generic car works at any count. Like expedition's
        # n_waypoints, an unbounded count means `sample()` and
        # `object_universe()` want a reduced space rather than the full one.
        mapping["n_gears"] = Integer("n_gears", (2, MAX_INT), default=3)
        # The distance to cover, the (>= (d) X) half of the goal.
        mapping["target_distance"] = Integer(
            "target_distance", (1, MAX_INT), default=100
        )
        # The fuel the car starts with.
        mapping["fuel"] = Integer("fuel", (0, MAX_INT), default=30)
        # The price of one unit of fuel in (:metric minimize (cost)). Every
        # gear shift adds 1 to cost, so beta is how many shifts a unit of fuel
        # is worth. At least 1, or the metric would not count fuel or time at
        # all (see generic_alpha).
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
            # Every instance minimises (cost), which sums a price per step and
            # a price per unit of fuel, so the metric belongs to the domain
            # rather than to a single instance. Problem.clone() copies it into
            # every instance.
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

        This is the only place the two variants differ.
        """
        if self.variant == "ipc":
            row = IPC_INSTANCES[params["index"]]
            return {**row, "car": IPC_CARS[row["n_gears"]]}
        n_gears = params["n_gears"]
        target = params["target_distance"]
        return {
            "n_gears": n_gears,
            "distance_min": target,
            "distance_max": target + GOAL_DISTANCE_TOLERANCE,
            "fuel": params["fuel"],
            "alpha": generic_alpha(params["fuel"], params["beta"]),
            "beta": params["beta"],
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
        # The car has to stop inside the distance window, back in first gear,
        # and it has to have driven at all (fuel_used > 0).
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
        # The car starts stopped at the origin in first gear, with every
        # counter at 0.
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
        # `current_gear` of the other gears defaults to false, and the shipped
        # instances do not list those either.
        return res

    def check_instance_parameters(self, params: Configuration):
        if self.variant == "ipc":
            return params["index"] in IPC_INSTANCES
        # Every generic configuration is accepted.
        #
        # TEMPORARILY DISABLED: the fuel has to be able to cover the distance.
        # This is a necessary condition, not a full solvability check: whether
        # the car can also stop exactly inside the goal window is left to the
        # planner, in the same spirit as the expedition port. The drive actions
        # require both v <= max_speed and v + a <= max_speed, so a step adds at
        # most 2 * max_speed, and the cheapest step is the top gear driven
        # inside its own band:
        #
        #     n_gears = params["n_gears"]
        #     cheapest_step = gear_fuel_aligned(n_gears, n_gears)
        #     longest_step = 2 * SPEED_PER_GEAR * n_gears
        #     if (params["fuel"] // cheapest_step) * longest_step < params[
        #         "target_distance"
        #     ]:
        #         return False
        #
        # It is off because it can leave a whole parameter space with nothing
        # acceptable in it, and `Generator.sample()` redraws until something is
        # accepted - so a space of, say, 2 units of fuel against 3 of distance
        # makes it spin with no way out. Whether upbm should allow spaces that
        # can do that is a question for the team; until it is settled, **an
        # instance may simply not have the fuel to finish, and nothing here will
        # say so.**
        return True
