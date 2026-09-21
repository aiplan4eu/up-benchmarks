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

# The car always starts stopped at the origin, in first gear, with nothing
# used up yet. These stay constants rather than becoming parameters: the goal
# demands v = 0, a = 0 and first gear at the *end*, so a different start would
# only add an offset to every instance.
START_DISTANCE = 0
START_SPEED = 0
START_ACCELERATION = 0

# No fuel table is allowed to reach zero: a free drive step would make any
# distance reachable on any budget, and a negative one is not a cost at all.
# The floor only bites past gear 10, far outside anything the dataset shows.
MIN_FUEL_COST = 1

# The values every one of the 20 shipped instances uses. They are the defaults
# of instance parameters rather than constants of the generator, because
# nothing in the domain fixes them - see `instance_parameter_space`. Keeping
# them as the defaults is what lets `sets/gear_car_ipc2026.yml` go on naming
# only the five parameters it always named.
IPC_MAX_ACCELERATION = 2
IPC_MIN_ACCELERATION = -1
IPC_ACC_STEP = 1
IPC_SPEED_PER_GEAR = 2
IPC_GOAL_DISTANCE_TOLERANCE = 2


def gear_speed_band(gear: int, speed_per_gear: int) -> tuple[int, int]:
    """Return (gear_v_min, gear_v_max) of a gear. Gears are 1-indexed.

    The bands tile [0, max_speed] and share their endpoints, so at the speed
    where one gear ends and the next begins either of the two is "aligned".
    """
    return (speed_per_gear * (gear - 1), speed_per_gear * gear)


def gear_max_acceleration(gear: int, n_gears: int, max_acceleration: int) -> int:
    """Return the acceleration ceiling of a gear.

    First gear pulls as hard as the car can, the top gear cannot accelerate at
    all - which is what makes shifting up the only way to go fast - and every
    gear between them gets a single step. In the IPC set the car's own
    `max_acceleration` is 2, which is why first gear reads 2 there.

    Note the top gear's 0 does *not* force the car to shift back down to stop:
    `gear_min_acceleration` is negative in the top gear too, so it can brake
    there. What forces the downshift is the goal asking for first gear.
    """
    if gear == 1:
        return max_acceleration
    if gear == n_gears:
        return 0
    return min(1, max_acceleration)


def gear_fuel_aligned(gear: int) -> int:
    """Fuel burnt per step when the speed is inside the gear's band.

    The shipped values are 11, 9, 8, 7, 6 for gears 1 to 5: higher gears are
    more efficient, and first gear is a step worse than the trend.
    """
    return max(MIN_FUEL_COST, 11 if gear == 1 else 11 - gear)


def gear_fuel_under(gear: int) -> int:
    """Fuel burnt per step when the speed is below the gear's band.

    Flat 17, with first gear again a step worse. It needs no floor, and first
    gear's 18 is never actually read: gear 1's band starts at 0 and every
    drive action requires v >= 0, so `(< (v) (gear_v_min g1))` cannot hold.
    """
    return 18 if gear == 1 else 17


def gear_fuel_over(gear: int, n_gears: int) -> int:
    """Fuel burnt per step when the speed is above the gear's band.

    This is the one table that depends on how many gears the car has: with
    more gears every over-revving step is penalised more. Verified against all
    four gear counts of the IPC set (2, 3, 4 and 5 gears).

    The top gear's entry is never read either - its band ends exactly at
    `max_speed`, which every drive action caps the speed at, so nothing can be
    "over" the top gear.
    """
    if gear == 1:
        return max(MIN_FUEL_COST, 15 + n_gears)
    return max(MIN_FUEL_COST, 16 + n_gears - 2 * gear)


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
        # The IPC set uses 2, 3, 4 and 5 gears, and the per-gear rules are
        # verified against all four; there is no upper bound because nothing in
        # the domain has one and the rules are floored to stay meaningful at any
        # count. Two is the fewest that makes gear_up/gear_down exist at all.
        # Like expedition's n_waypoints, an unbounded count means `sample()` and
        # `object_universe()` want a reduced space rather than the full one.
        mapping["n_gears"] = Integer("n_gears", (2, MAX_INT), default=2)
        # The distance to cover, the (>= (d) X) half of the goal.
        mapping["target_distance"] = Integer(
            "target_distance", (1, MAX_INT), default=260
        )
        mapping["fuel"] = Integer("fuel", (0, MAX_INT), default=406)
        # How wide a speed band each gear covers, so max_speed is
        # speed_per_gear * n_gears. This is the scale knob of the whole domain:
        # a drive step adds at most 2 * max_speed to the distance, so it decides
        # how far a tank of fuel can go.
        mapping["speed_per_gear"] = Integer(
            "speed_per_gear", (1, MAX_INT), default=IPC_SPEED_PER_GEAR
        )
        # The goal asks for a distance in [target, target + tolerance]. It looks
        # cosmetic and is not: a drive step adds (2v + a) and a plan that starts
        # and ends stopped has its accelerations sum to zero, so the distance
        # reached is ALWAYS EVEN, whatever the gearbox.
        #
        # That is why the lower bound is 1 rather than 0, and it costs nothing:
        # for an even target the window [X, X+1] holds exactly one even value,
        # X, so it means the same as a window of 0; for an odd target a window
        # of 0 could never be met at all. Keeping 0 out of the space therefore
        # removes a whole class of unsolvable instance without removing a single
        # reachable one - the parameter space doing the work instead of a check.
        mapping["goal_distance_tolerance"] = Integer(
            "goal_distance_tolerance", (1, MAX_INT), default=IPC_GOAL_DISTANCE_TOLERANCE
        )
        # The car's own acceleration limits. Every action conjoins these with the
        # per-gear ones, so whichever is tighter binds; in the IPC set they are
        # exactly the per-gear values, which is why the shipped instances give no
        # sign of which one is doing the work.
        mapping["max_acceleration"] = Integer(
            "max_acceleration", (1, MAX_INT), default=IPC_MAX_ACCELERATION
        )
        mapping["min_acceleration"] = Integer(
            "min_acceleration", (-MAX_INT, -1), default=IPC_MIN_ACCELERATION
        )
        # How much one accelerate/decelerate changes the acceleration by. Raising
        # it without raising the per-gear ceilings leaves first gear as the only
        # one that can accelerate, which check_instance_parameters catches.
        mapping["acc_step"] = Integer("acc_step", (1, MAX_INT), default=IPC_ACC_STEP)
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
        # NOTE on sampling this space, which now carries four conditions rather
        # than one. `Generator.sample()` redraws until check_instance_parameters
        # accepts, so it needs a space holding something acceptable: from the
        # full space above that is about a third of draws, but a reduced space
        # built from the *lower bounds* of these ranges holds nothing valid at
        # all - 2 units of fuel cannot cover 3 of distance - and the redraw loop
        # then never ends. Build a reduced space around the defaults rather than
        # the bounds. 2048 documents the same hazard for a different reason.
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
            LE(self._d(), target + params["goal_distance_tolerance"]),
            self._current_gear(self._gear(1)),
            Equals(self._v(), 0),
            Equals(self._a(), 0),
            GE(self._fuel(), 0),
            GT(self._fuel_used(), 0),
        ]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        n_gears = params["n_gears"]
        max_acceleration = params["max_acceleration"]
        min_acceleration = params["min_acceleration"]
        speed_per_gear = params["speed_per_gear"]
        res: dict[FNode, FNode] = {
            self._current_gear(self._gear(1)): TRUE(),
            self._d(): START_DISTANCE,
            self._v(): START_SPEED,
            self._a(): START_ACCELERATION,
            self._max_acceleration(): max_acceleration,
            self._min_acceleration(): min_acceleration,
            self._max_speed(): speed_per_gear * n_gears,
            self._acc_step(): params["acc_step"],
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
            v_min, v_max = gear_speed_band(i, speed_per_gear)
            res[self._gear_v_min(gear)] = v_min
            res[self._gear_v_max(gear)] = v_max
            res[self._gear_min_acceleration(gear)] = min_acceleration
            res[self._gear_max_acceleration(gear)] = gear_max_acceleration(
                i, n_gears, max_acceleration
            )
            res[self._gear_fuel_aligned(gear)] = gear_fuel_aligned(i)
            res[self._gear_fuel_under(gear)] = gear_fuel_under(i)
            res[self._gear_fuel_over(gear)] = gear_fuel_over(i, n_gears)
            if i < n_gears:
                res[self._gear_next(gear, self._gear(i + 1))] = TRUE()
        # `current_gear` of the other gears defaults to false, and the shipped
        # instances do not list those either.
        return res

    def check_instance_parameters(self, params: Configuration):
        # These are necessary conditions, not a full solvability check: whether
        # the car can also stop exactly inside the goal window is left to the
        # planner, in the same spirit as the expedition port.
        acc_step = params["acc_step"]

        # 1. The car has to be able to accelerate at all, or it never leaves the
        # origin. `accelerate` needs a + acc_step within both the car's ceiling
        # and the gear's, and first gear's ceiling *is* the car's.
        if acc_step > params["max_acceleration"]:
            return False

        # 2. And to brake, or it can never satisfy the goal's v = 0 again. From
        # a = 0 one `decelerate` reaches -acc_step, which both the car's floor
        # and the gear's floor have to allow.
        if params["min_acceleration"] > -acc_step:
            return False

        # The distance parity condition that used to live here is gone, and not
        # because it was wrong: `goal_distance_tolerance` starts at 1 now, which
        # makes it impossible to violate. See the parameter.

        # TEMPORARILY DISABLED: the fuel has to be able to cover the distance.
        # The drive actions require both v <= max_speed and v + a <= max_speed,
        # so a step adds at most 2 * max_speed, and the cheapest step is the top
        # gear driven inside its own band:
        #
        #     cheapest_step = gear_fuel_aligned(n_gears)
        #     longest_step = 2 * params["speed_per_gear"] * n_gears
        #     if (params["fuel"] // cheapest_step) * longest_step < target:
        #         return False
        #
        # It is off because it is the one condition here that can leave a whole
        # parameter space with nothing acceptable in it, and `Generator.sample()`
        # redraws until something is accepted - so a space of, say, 2 units of
        # fuel against 3 of distance makes it spin with no way out. Whether upbm
        # should allow spaces that can do that is a question for the team; until
        # it is settled, **an instance may simply not have the fuel to finish,
        # and nothing here will say so.** That is a weaker promise than before,
        # but in the same spirit as the rest: the check was already necessary
        # rather than sufficient, since whether the car can stop inside the goal
        # window was always left to the planner, exactly as expedition does it.
        return True
