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

from fractions import Fraction
from pathlib import Path
from typing import Any, List, Optional, Tuple

from ConfigSpace import (
    ConfigurationSpace,
    Configuration,
    Integer,
    Categorical,
    Constant,
)
from unified_planning.io import PDDLReader
from unified_planning.model import Problem, Object, FNode
from unified_planning.shortcuts import Real

from upbm.generator import Generator
from upbm.utils import MAX_INT, is_subspace, hyperparam_range


SCRIPT_PATH = Path(__file__).absolute().parent
RESOURCES_PATH = SCRIPT_PATH / "resources"

# The boat polar table: how fast the boat can go at each angle to the wind.
# Every instance of the IPC set, in both variants, uses exactly these values.
# vmax_0 is 0 because a sail boat cannot sail straight into the wind.
POLAR_TABLE = {
    0: Fraction("0"),
    15: Fraction("0.17"),
    30: Fraction("0.3"),
    45: Fraction("0.45"),
    60: Fraction("0.65"),
    75: Fraction("1"),
    90: Fraction("1.49"),
    105: Fraction("1.44"),
    120: Fraction("1.37"),
    135: Fraction("1.26"),
    150: Fraction("1.12"),
    165: Fraction("0.96"),
    180: Fraction("0.8"),
}

# How much of its previous speed the boat keeps when it changes heading. The
# opt instances all use 0.5 and the sat instances all use 0.9, so this is what
# actually separates the two variants: a boat that keeps 90% of its speed is
# much slower to slow down, and stopping next to the person is the hard part.
VARIANT_INERTIA = {
    "opt": Fraction("0.5"),
    "sat": Fraction("0.9"),
}

# The boat always starts at the origin, stopped, pointing at 0 degrees.
BOAT_START_X = Fraction(0)
BOAT_START_Y = Fraction(0)
BOAT_START_V = Fraction(0)
BOAT_START_ANGLE = 0

# --- opt placement ---------------------------------------------------------
# The 20 opt instances put the single person on a straight diagonal ramp:
# problem_N has the person at (5 + 0.4 N, 15.5 + 0.4 N), for N = 0..19. Both
# coordinates grow by the same amount, so the person drifts away from the boat
# along a 45 degree line.
OPT_FIRST_X = Fraction("5")
OPT_FIRST_Y = Fraction("15.5")
OPT_STEP = Fraction("0.4")

# --- sat placement ---------------------------------------------------------
# The sat instances put every person on a circle of radius 100 around the boat,
# at a multiple of 45 degrees, with the coordinates rounded to whole numbers
# (100 * cos(45 degrees) is 70.71, which the dataset writes as 71). These eight
# points are the only person positions the sat set ever uses. A person is
# picked by its index in this list, so direction i sits at 45 * i degrees.
SAT_POSITIONS = [
    (100, 0),  # 0 degrees
    (71, 71),  # 45
    (0, 100),  # 90
    (-71, 71),  # 135
    (-100, 0),  # 180
    (-71, -71),  # 225
    (0, -100),  # 270
    (71, -71),  # 315
]
# The second person is optional: the sat set has instances with one person and
# instances with two, and never more than two. This is the direction value that
# means "there is no second person".
NO_PERSON = -1


class SailingWindGenerator(Generator):
    @staticmethod
    def get_domain_parameter_space():
        mapping: dict[str, Any] = {}
        mapping["version"] = Constant("version", 1)
        # The IPC dataset ships sailing-wind twice, as an optimal and a
        # satisficing track. The two domain files are identical, so both
        # variants share one skeleton and differ in how the instances are laid
        # out: see VARIANT_INERTIA and the placement rules above.
        mapping["variant"] = Categorical(
            "variant",
            ["opt", "sat"],
            default="opt",
        )
        return ConfigurationSpace(name=mapping)

    def __init__(self, domain_params: Configuration):
        domain_params.check_valid_configuration()
        if (
            domain_params.config_space
            != SailingWindGenerator.get_domain_parameter_space()
        ):
            raise ValueError(f"Invalid domain parameters: {domain_params}")

        self.version = domain_params["version"]
        self.variant = domain_params["variant"]
        self._domain = self._mk_domain()
        assert isinstance(self._domain, Problem)
        self._Boat = self._domain.user_type("boat")
        self._Person = self._domain.user_type("person")
        self._x = self._domain.fluent("x")
        self._y = self._domain.fluent("y")
        self._v = self._domain.fluent("v")
        self._r = self._domain.fluent("r")
        self._sailing_angle = self._domain.fluent("sailing-angle")
        self._saved = self._domain.fluent("saved")

        self._object_cache: dict[tuple[str, Any], Object] = {}
        super().__init__(domain_params)

    @property
    def instance_parameter_space(self) -> ConfigurationSpace:
        mapping: dict[str, Any] = {}
        if self.variant == "opt":
            # step 0 to 19 reproduces the 20 shipped opt instances
            mapping["step"] = Integer("step", (0, MAX_INT), default=0)
        elif self.variant == "sat":
            # One parameter per person, holding the index into SAT_POSITIONS of
            # the point on the circle where that person waits. The second one
            # may be NO_PERSON, which reproduces the single person instances.
            mapping["direction_0"] = Integer(
                "direction_0", (0, len(SAT_POSITIONS) - 1), default=2
            )
            mapping["direction_1"] = Integer(
                "direction_1", (NO_PERSON, len(SAT_POSITIONS) - 1), default=NO_PERSON
            )
        else:
            raise ValueError(f"invalid variant {self.variant}")
        return ConfigurationSpace(name=mapping)

    @property
    def name(self) -> str:
        return f"SailingWind V{self.version} ({self.variant})"

    @property
    def domain(self) -> Problem:
        return self._domain

    def _mk_domain(self):
        if self.version == 1:
            reader = PDDLReader()
            # Both variants read the same file: the opt and sat domains of the
            # IPC dataset are byte-identical. The instances carry no metric
            # (the :metric line is commented out in every shipped file), so no
            # quality metric is attached here either.
            return reader.parse_problem(
                str(RESOURCES_PATH / f"sailing_wind_v{self.version}.pddl")
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

    @staticmethod
    def _number(value: Fraction):
        """Write whole numbers as integers, like the shipped instances do.

        The fluents are all real, but the dataset writes `(= (x b0) 0)` rather
        than `0.0`, and UP keeps the distinction when it writes the PDDL back
        out. Values are equal either way, this only keeps the generated files
        looking like the originals.
        """
        return int(value) if value.denominator == 1 else Real(value)

    def _person_positions(self, params) -> List[Tuple[Fraction, Fraction]]:
        """Return the (x, y) position of every person of this instance."""
        if self.variant == "opt":
            offset = OPT_STEP * params["step"]
            return [(OPT_FIRST_X + offset, OPT_FIRST_Y + offset)]
        elif self.variant == "sat":
            res = []
            for key in ("direction_0", "direction_1"):
                direction = params[key]
                if direction == NO_PERSON:
                    continue
                x, y = SAT_POSITIONS[direction]
                res.append((Fraction(x), Fraction(y)))
            return res
        raise ValueError(f"invalid variant {self.variant}")

    def get_objects(self, params) -> List[Object]:
        self._check_params(params)
        if not self.check_instance_parameters(params):
            raise ValueError(f"Requested instance is unsolvable")
        objs: List[Object] = [self._get_object("b0", self._Boat)]
        for i in range(len(self._person_positions(params))):
            objs.append(self._get_object(f"p{i}", self._Person))
        return objs

    def object_universe(
        self, instance_parameters_space: Optional[ConfigurationSpace] = None
    ):
        if instance_parameters_space is None:
            instance_parameters_space = self.instance_parameter_space
        if self.variant == "opt":
            # the ramp always carries a single person, wherever it stops
            n_persons = 1
        elif self.variant == "sat":
            # a second person only exists when direction_1 can be a real point
            _, second_upper = hyperparam_range(instance_parameters_space["direction_1"])
            n_persons = 2 if second_upper > NO_PERSON else 1
        else:
            raise ValueError(f"invalid variant {self.variant}")
        return [self._get_object("b0", self._Boat)] + [
            self._get_object(f"p{i}", self._Person) for i in range(n_persons)
        ]

    def get_goal(self, params) -> List[FNode]:
        self._check_params(params)
        # the only thing ever asked for is that every person is picked up
        return [
            self._saved(self._get_object(f"p{i}", self._Person))
            for i in range(len(self._person_positions(params)))
        ]

    def get_initial_state(self, params) -> dict[FNode, FNode]:
        self._check_params(params)
        boat = self._get_object("b0", self._Boat)
        res: dict[FNode, FNode] = {}
        for angle, vmax in POLAR_TABLE.items():
            res[self._domain.fluent(f"vmax_{angle}")(boat)] = self._number(vmax)
        res[self._x(boat)] = self._number(BOAT_START_X)
        res[self._y(boat)] = self._number(BOAT_START_Y)
        res[self._r(boat)] = self._number(VARIANT_INERTIA[self.variant])
        res[self._v(boat)] = self._number(BOAT_START_V)
        res[self._sailing_angle(boat)] = BOAT_START_ANGLE
        for i, (x, y) in enumerate(self._person_positions(params)):
            person = self._get_object(f"p{i}", self._Person)
            res[self._x(person)] = self._number(x)
            res[self._y(person)] = self._number(y)
        # `saved` is left out on purpose: the domain declares it with a default
        # of false, and the shipped instances do not list it either.
        return res

    def check_instance_parameters(self, params: Configuration):
        # The boat can turn by 15 degrees per move and can always shed speed by
        # heading into the wind (vmax_0 is 0), so it can reach any point on the
        # plane and stop there, and the rescue box around a person is a
        # generous 30 by 30. Every position these parameters can produce is
        # therefore reachable, which is why nothing is rejected here.
        return True
